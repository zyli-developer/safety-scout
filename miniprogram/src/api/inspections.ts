/**
 * Safety Scout API：POST 创建巡检任务 / GET 查询任务状态。
 *
 * createInspection 接受两种入参：
 * - string (Taro tempFilePath)：走 Taro.uploadFile —— 移动端 / weapp 路径
 * - File (浏览器原生)：走 FormData + fetch —— 桌面 H5 通过 <input type="file"> 拿到的对象
 *
 * v1 / v2 灰度（plan §5.2 + docs/specs/v2-rollout.md §一）：
 * - 由 `V2_TRAFFIC_SHARE` 决定本次请求走哪个 API；调用方不感知
 * - 返回的 `schema_version` 字段告诉 caller 本次落在哪条路径，由 caller 写到
 *   报告页 URL（`?v=2`），让 `getInspection` 知道去哪查 GET
 * - 两条路径 wire-format 顶层完全一致（inspection_id / poll_url / poll_interval_ms /
 *   timeout_ms / status），上传成功路径无需分支
 */
import Taro from '@tarojs/taro';
import { API_BASE_URL, V2_TRAFFIC_SHARE } from '../config';
import { ApiError, request } from './client';
import type {
  CreateInspectionResponse,
  GetInspectionResponse,
  ErrorBody,
} from '../types/inspection';
import type {
  GetInspectionV2Response,
  SchemaVersion,
} from '../types/inspection-v2';

/** 内部决定本次请求走 v1 还是 v2 —— 提取为函数便于单测注入。 */
export function pickSchemaVersion(): SchemaVersion {
  return Math.random() < V2_TRAFFIC_SHARE ? 'v2' : 'v1';
}

/** 端点路径表 —— 把 URL 字面量收敛在一处。 */
function createEndpoint(version: SchemaVersion): string {
  return version === 'v2' ? '/api/v2/analyze' : '/api/v1/inspections';
}

function getEndpoint(version: SchemaVersion, id: string): string {
  return version === 'v2'
    ? `/api/v2/inspections/${id}`
    : `/api/v1/inspections/${id}`;
}

/** createInspection 的返回值 —— 在原响应上附加本次实际走的版本。 */
export type CreateInspectionResult = CreateInspectionResponse & {
  schema_version: SchemaVersion;
};

export function createInspection(
  input: string | File,
  versionOverride?: SchemaVersion,
): Promise<CreateInspectionResult> {
  const version = versionOverride ?? pickSchemaVersion();
  if (typeof input === 'string') {
    return createFromTempFilePath(input, version);
  }
  return createFromFile(input, version);
}

function createFromTempFilePath(
  imageTempFilePath: string,
  version: SchemaVersion,
): Promise<CreateInspectionResult> {
  return new Promise((resolve, reject) => {
    Taro.uploadFile({
      url: API_BASE_URL + createEndpoint(version),
      filePath: imageTempFilePath,
      name: 'image',
      success: (res) => {
        let body: unknown = null;
        try {
          body = JSON.parse(res.data);
        } catch {
          // body 不是 JSON，下面统一用 fallback 文案
        }
        if (res.statusCode >= 400) {
          const err = (body as { error?: ErrorBody } | null)?.error;
          reject(
            new ApiError(
              err?.code ?? 'UPLOAD_FAILED',
              err?.user_message ?? '图片上传失败，请重试',
              res.statusCode,
            ),
          );
          return;
        }
        resolve({
          ...(body as CreateInspectionResponse),
          schema_version: version,
        });
      },
      fail: () =>
        reject(new ApiError('NETWORK_ERROR', '网络异常，请检查后重试', 0)),
    });
  });
}

async function createFromFile(
  file: File,
  version: SchemaVersion,
): Promise<CreateInspectionResult> {
  const form = new FormData();
  form.append('image', file);

  let resp: Response;
  try {
    resp = await fetch(API_BASE_URL + createEndpoint(version), {
      method: 'POST',
      body: form,
    });
  } catch {
    throw new ApiError('NETWORK_ERROR', '网络异常，请检查后重试', 0);
  }

  if (!resp.ok) {
    let body: { error?: ErrorBody } | null = null;
    try {
      body = (await resp.json()) as { error?: ErrorBody };
    } catch {
      // 非 JSON body，用 fallback
    }
    throw new ApiError(
      body?.error?.code ?? 'UPLOAD_FAILED',
      body?.error?.user_message ?? '图片上传失败，请重试',
      resp.status,
    );
  }
  const data = (await resp.json()) as CreateInspectionResponse;
  return { ...data, schema_version: version };
}

/**
 * GET /api/{v}/inspections/{id}。
 *
 * 默认 v1（与历史调用兼容）；v2 调用者必须显式传 'v2'。
 * 返回类型仍是 GetInspectionResponse —— v2 的 report 形状不同，调用方负责
 * 在拿到结果后判别（v1: `report.hazards`; v2: `report.findings`）。
 */
export function getInspection(
  id: string,
  version: SchemaVersion = 'v1',
): Promise<GetInspectionResponse | GetInspectionV2Response> {
  return request<GetInspectionResponse | GetInspectionV2Response>({
    url: getEndpoint(version, id),
    method: 'GET',
  });
}

/**
 * POST /api/v2/inspections/{id}/feedback —— badcase 反馈通路。
 *
 * 仅 v2 inspection 有 feedback 端点（v1 没有 check_id 概念）。
 * 用户在报告页点"误报 / 漏报 / 整改建议不可执行"时调用。
 */
export interface FeedbackPayload {
  kind: 'false_positive' | 'missed' | 'bad_action';
  check_id?: string;
  description: string;
}

export interface FeedbackResponse {
  feedback_id: string;
  inspection_id: string;
  created_at: string;
}

export function submitFeedback(
  inspectionId: string,
  body: FeedbackPayload,
): Promise<FeedbackResponse> {
  return request<FeedbackResponse>({
    url: `/api/v2/inspections/${inspectionId}/feedback`,
    method: 'POST',
    data: body,
  });
}

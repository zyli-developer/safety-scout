/**
 * Safety Scout API：POST 创建巡检任务 / GET 查询任务状态。
 *
 * createInspection 接受两种入参：
 * - string (Taro tempFilePath)：走 Taro.uploadFile —— 移动端 / weapp 路径
 * - File (浏览器原生)：走 FormData + fetch —— 桌面 H5 通过 <input type="file"> 拿到的对象
 *
 * 两条路径返回相同形状的 CreateInspectionResponse，错误统一归一为 ApiError。
 */
import Taro from '@tarojs/taro';
import { API_BASE_URL } from '../config';
import { ApiError, request } from './client';
import type {
  CreateInspectionResponse,
  GetInspectionResponse,
  ErrorBody,
} from '../types/inspection';

export function createInspection(
  input: string | File,
): Promise<CreateInspectionResponse> {
  if (typeof input === 'string') {
    return createFromTempFilePath(input);
  }
  return createFromFile(input);
}

function createFromTempFilePath(
  imageTempFilePath: string,
): Promise<CreateInspectionResponse> {
  return new Promise((resolve, reject) => {
    Taro.uploadFile({
      url: API_BASE_URL + '/api/v1/inspections',
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
        resolve(body as CreateInspectionResponse);
      },
      fail: () =>
        reject(new ApiError('NETWORK_ERROR', '网络异常，请检查后重试', 0)),
    });
  });
}

async function createFromFile(file: File): Promise<CreateInspectionResponse> {
  const form = new FormData();
  form.append('image', file);

  let resp: Response;
  try {
    resp = await fetch(API_BASE_URL + '/api/v1/inspections', {
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
  return (await resp.json()) as CreateInspectionResponse;
}

export function getInspection(id: string): Promise<GetInspectionResponse> {
  return request<GetInspectionResponse>({
    url: `/api/v1/inspections/${id}`,
    method: 'GET',
  });
}

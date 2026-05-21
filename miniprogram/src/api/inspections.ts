/**
 * Safety Scout API：POST 创建巡检任务 / GET 查询任务状态。
 *
 * 之所以 createInspection 不走 client.request：Taro.request 不直接支持
 * multipart/form-data 文件上传，必须用专门的 Taro.uploadFile。所以这里手写
 * 一遍同样的错误归一逻辑，结果就是和 client.ts 一致的 ApiError 形状。
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
  imageTempFilePath: string,
): Promise<CreateInspectionResponse> {
  return new Promise((resolve, reject) => {
    Taro.uploadFile({
      url: API_BASE_URL + '/api/v1/inspections',
      filePath: imageTempFilePath,
      name: 'image',
      success: (res) => {
        // Taro.uploadFile 的 res.data 永远是 string；后端虽然返 JSON，但
        // 4xx / 5xx 时也可能返 HTML（例如反向代理给出的 500 页），做兜底解析。
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

export function getInspection(id: string): Promise<GetInspectionResponse> {
  return request<GetInspectionResponse>({
    url: `/api/v1/inspections/${id}`,
    method: 'GET',
  });
}

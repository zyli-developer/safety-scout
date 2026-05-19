/** 单元测试：client.request 的归一化和 ApiError 形状。 */
import Taro from '@tarojs/taro';
import { ApiError, request } from '../../src/api/client';
import { API_BASE_URL } from '../../src/config';

const mockedRequest = Taro.request as unknown as jest.Mock;

describe('api/client.request', () => {
  beforeEach(() => {
    mockedRequest.mockReset();
  });

  it('returns parsed body on 2xx', async () => {
    mockedRequest.mockResolvedValueOnce({
      statusCode: 200,
      data: { foo: 'bar' },
    });

    const r = await request<{ foo: string }>({
      url: '/whatever',
      method: 'GET',
    });
    expect(r).toEqual({ foo: 'bar' });
  });

  it('throws ApiError on 4xx with full error envelope', async () => {
    mockedRequest.mockResolvedValueOnce({
      statusCode: 400,
      data: {
        error: {
          code: 'INVALID_IMAGE',
          message: 'dev-side detail',
          user_message: '图片格式不支持',
        },
      },
    });

    await expect(
      request({ url: '/x', method: 'POST', data: {} }),
    ).rejects.toMatchObject({
      name: 'ApiError',
      code: 'INVALID_IMAGE',
      userMessage: '图片格式不支持',
      statusCode: 400,
    });
  });

  it('falls back to UNKNOWN + default zh message when error body missing', async () => {
    mockedRequest.mockResolvedValueOnce({
      statusCode: 500,
      data: {},
    });

    await expect(request({ url: '/x', method: 'GET' })).rejects.toMatchObject({
      code: 'UNKNOWN',
      userMessage: '网络异常，请重试',
      statusCode: 500,
    });
  });

  it('throws NETWORK_ERROR when Taro.request rejects', async () => {
    mockedRequest.mockRejectedValueOnce(new Error('dns boom'));

    await expect(request({ url: '/x', method: 'GET' })).rejects.toMatchObject({
      code: 'NETWORK_ERROR',
      statusCode: 0,
    });
  });

  it('passes url / method / timeout through to Taro.request', async () => {
    mockedRequest.mockResolvedValueOnce({ statusCode: 200, data: {} });

    await request({
      url: '/api/v1/inspections/abc',
      method: 'GET',
      timeoutMs: 5_000,
    });

    expect(mockedRequest).toHaveBeenCalledTimes(1);
    const call = mockedRequest.mock.calls[0][0];
    expect(call.url).toBe(API_BASE_URL + '/api/v1/inspections/abc');
    expect(call.method).toBe('GET');
    expect(call.timeout).toBe(5_000);
    expect(call.header).toEqual({ 'Content-Type': 'application/json' });
  });

  it('ApiError carries code/userMessage/statusCode and is instanceof Error', () => {
    const e = new ApiError('X', 'Y', 429);
    expect(e).toBeInstanceOf(Error);
    expect(e).toBeInstanceOf(ApiError);
    expect(e.code).toBe('X');
    expect(e.userMessage).toBe('Y');
    expect(e.statusCode).toBe(429);
    expect(e.message).toBe('Y');
    expect(e.name).toBe('ApiError');
  });
});

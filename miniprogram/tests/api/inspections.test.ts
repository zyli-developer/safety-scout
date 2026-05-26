/** 单元测试：createInspection / getInspection 的成功/失败路径。 */
import Taro from '@tarojs/taro';
import { createInspection, getInspection } from '../../src/api/inspections';
import { API_BASE_URL } from '../../src/config';

const mockedUploadFile = Taro.uploadFile as unknown as jest.Mock;
const mockedRequest = Taro.request as unknown as jest.Mock;

describe('api/inspections.createInspection', () => {
  beforeEach(() => {
    mockedUploadFile.mockReset();
  });

  it('resolves with parsed body on 2xx success', async () => {
    const payload = {
      inspection_id: 'id-1',
      poll_url: '/api/v1/inspections/id-1',
      poll_interval_ms: 2000,
      timeout_ms: 330_000,
      status: 'queued',
    };
    mockedUploadFile.mockImplementationOnce((opts) => {
      opts.success({ statusCode: 200, data: JSON.stringify(payload) });
    });

    // createInspection 在 wire payload 基础上附加 schema_version（前端决策，非来自服务端）
    const res = await createInspection('/tmp/foo.jpg', 'v1');
    expect(res).toEqual({ ...payload, schema_version: 'v1' });
  });

  it('rejects with ApiError carrying server error code on 4xx', async () => {
    mockedUploadFile.mockImplementationOnce((opts) => {
      opts.success({
        statusCode: 400,
        data: JSON.stringify({
          error: {
            code: 'INVALID_IMAGE',
            message: 'unsupported',
            user_message: '图片格式不支持',
          },
        }),
      });
    });

    await expect(createInspection('/tmp/x.jpg')).rejects.toMatchObject({
      name: 'ApiError',
      code: 'INVALID_IMAGE',
      userMessage: '图片格式不支持',
      statusCode: 400,
    });
  });

  it('falls back to UPLOAD_FAILED when 4xx body is not JSON', async () => {
    mockedUploadFile.mockImplementationOnce((opts) => {
      opts.success({ statusCode: 500, data: '<html>500 Internal</html>' });
    });

    await expect(createInspection('/tmp/x.jpg')).rejects.toMatchObject({
      code: 'UPLOAD_FAILED',
      userMessage: '图片上传失败，请重试',
      statusCode: 500,
    });
  });

  it('rejects NETWORK_ERROR when fail callback fires', async () => {
    mockedUploadFile.mockImplementationOnce((opts) => {
      opts.fail({ errMsg: 'uploadFile:fail' });
    });

    await expect(createInspection('/tmp/x.jpg')).rejects.toMatchObject({
      code: 'NETWORK_ERROR',
      statusCode: 0,
    });
  });

  it('passes name="image" multipart key and correct url to Taro.uploadFile', async () => {
    mockedUploadFile.mockImplementationOnce((opts) => {
      opts.success({
        statusCode: 200,
        data: JSON.stringify({
          inspection_id: 'id-2',
          poll_url: '/api/v1/inspections/id-2',
          poll_interval_ms: 2000,
          timeout_ms: 330_000,
          status: 'queued',
        }),
      });
    });

    await createInspection('/tmp/photo.png');
    expect(mockedUploadFile).toHaveBeenCalledTimes(1);
    const call = mockedUploadFile.mock.calls[0][0];
    expect(call.url).toBe(API_BASE_URL + '/api/v1/inspections');
    expect(call.filePath).toBe('/tmp/photo.png');
    expect(call.name).toBe('image');
  });
});

describe('api/inspections.getInspection', () => {
  beforeEach(() => {
    mockedRequest.mockReset();
  });

  it('delegates to request with correct url + method', async () => {
    mockedRequest.mockResolvedValueOnce({
      statusCode: 200,
      data: {
        inspection_id: 'abc-123',
        status: 'queued',
        created_at: '2026-05-19T00:00:00Z',
        updated_at: '2026-05-19T00:00:00Z',
        report: null,
        error: null,
      },
    });

    const res = await getInspection('abc-123');
    expect(res.inspection_id).toBe('abc-123');
    expect(mockedRequest).toHaveBeenCalledTimes(1);
    const call = mockedRequest.mock.calls[0][0];
    expect(call.url).toBe(API_BASE_URL + '/api/v1/inspections/abc-123');
    expect(call.method).toBe('GET');
  });
});

describe('api/inspections.createInspection — File input (desktop H5)', () => {
  let originalFetch: typeof globalThis.fetch;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('uses FormData + fetch when given a File, resolves on 2xx', async () => {
    const payload = {
      inspection_id: 'desk-1',
      poll_url: '/api/v1/inspections/desk-1',
      poll_interval_ms: 2000,
      timeout_ms: 330_000,
      status: 'queued',
    };
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    const file = new File([new Uint8Array([0xff, 0xd8, 0xff])], 'photo.jpg', {
      type: 'image/jpeg',
    });
    const res = await createInspection(file, 'v1');
    expect(res).toEqual({ ...payload, schema_version: 'v1' });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toBe(API_BASE_URL + '/api/v1/inspections');
    expect(init.method).toBe('POST');
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get('image')).toBeInstanceOf(File);
  });

  it('rejects ApiError with server error code on 4xx', async () => {
    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({
        error: {
          code: 'INVALID_IMAGE',
          message: 'bad mime',
          user_message: '图片格式不支持',
        },
      }),
      text: async () => '{}',
    }) as unknown as typeof globalThis.fetch;

    const file = new File([new Uint8Array([0])], 'x.bin', { type: 'application/octet-stream' });
    await expect(createInspection(file)).rejects.toMatchObject({
      name: 'ApiError',
      code: 'INVALID_IMAGE',
      statusCode: 400,
    });
  });

  it('rejects NETWORK_ERROR on fetch reject', async () => {
    globalThis.fetch = jest.fn().mockRejectedValue(new Error('boom')) as unknown as typeof globalThis.fetch;
    const file = new File([new Uint8Array([0])], 'x.jpg', { type: 'image/jpeg' });
    await expect(createInspection(file)).rejects.toMatchObject({
      code: 'NETWORK_ERROR',
      statusCode: 0,
    });
  });
});

describe('api/inspections — v1/v2 路径分支 (V2_TRAFFIC_SHARE)', () => {
  beforeEach(() => {
    mockedUploadFile.mockReset();
    mockedRequest.mockReset();
  });

  it('createInspection(versionOverride="v2") 用 tempFilePath 走 /api/v2/analyze', async () => {
    mockedUploadFile.mockImplementationOnce((opts) => {
      opts.success({
        statusCode: 200,
        data: JSON.stringify({
          inspection_id: 'v2-id',
          poll_url: '/api/v2/inspections/v2-id',
          poll_interval_ms: 2000,
          timeout_ms: 390_000,
          status: 'queued',
        }),
      });
    });

    const res = await createInspection('/tmp/x.jpg', 'v2');
    expect(res.schema_version).toBe('v2');
    expect(res.poll_url).toBe('/api/v2/inspections/v2-id');
    expect(mockedUploadFile.mock.calls[0][0].url).toBe(API_BASE_URL + '/api/v2/analyze');
  });

  it('createInspection(versionOverride="v2") 用 File 走 /api/v2/analyze', async () => {
    const payload = {
      inspection_id: 'v2-desk',
      poll_url: '/api/v2/inspections/v2-desk',
      poll_interval_ms: 2000,
      timeout_ms: 390_000,
      status: 'queued',
    };
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });
    globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;

    const file = new File([new Uint8Array([0xff])], 'p.jpg', { type: 'image/jpeg' });
    const res = await createInspection(file, 'v2');
    expect(res.schema_version).toBe('v2');
    const [url] = fetchMock.mock.calls[0];
    expect(String(url)).toBe(API_BASE_URL + '/api/v2/analyze');
  });

  it('getInspection(id, "v2") 命中 /api/v2/inspections/{id}', async () => {
    mockedRequest.mockResolvedValueOnce({
      statusCode: 200,
      data: {
        inspection_id: 'v2-id',
        status: 'queued',
        created_at: '2026-05-26T00:00:00Z',
        updated_at: '2026-05-26T00:00:00Z',
        report: null,
        error: null,
      },
    });

    await getInspection('v2-id', 'v2');
    const call = mockedRequest.mock.calls[0][0];
    expect(call.url).toBe(API_BASE_URL + '/api/v2/inspections/v2-id');
  });

  it('getInspection 默认 v1 —— 兼容历史调用', async () => {
    mockedRequest.mockResolvedValueOnce({
      statusCode: 200,
      data: {
        inspection_id: 'v1-id',
        status: 'queued',
        created_at: '',
        updated_at: '',
        report: null,
        error: null,
      },
    });

    await getInspection('v1-id');
    const call = mockedRequest.mock.calls[0][0];
    expect(call.url).toBe(API_BASE_URL + '/api/v1/inspections/v1-id');
  });
});

describe('api/inspections.submitFeedback', () => {
  beforeEach(() => {
    mockedRequest.mockReset();
  });

  it('POSTs to /api/v2/inspections/{id}/feedback with body', async () => {
    mockedRequest.mockResolvedValueOnce({
      statusCode: 201,
      data: {
        feedback_id: 'fb-1',
        inspection_id: 'v2-id',
        created_at: '2026-05-26T00:00:00Z',
      },
    });

    // dynamic import to avoid top-of-file import (keeps deltas minimal)
    const { submitFeedback } = await import('../../src/api/inspections');
    const res = await submitFeedback('v2-id', {
      kind: 'false_positive',
      check_id: 'B01',
      description: '工人其实戴了安全带',
    });
    expect(res.feedback_id).toBe('fb-1');
    const call = mockedRequest.mock.calls[0][0];
    expect(call.url).toBe(API_BASE_URL + '/api/v2/inspections/v2-id/feedback');
    expect(call.method).toBe('POST');
    expect(call.data).toEqual({
      kind: 'false_positive',
      check_id: 'B01',
      description: '工人其实戴了安全带',
    });
  });
});

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

    const res = await createInspection('/tmp/foo.jpg');
    expect(res).toEqual(payload);
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
    const res = await createInspection(file);
    expect(res).toEqual(payload);

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

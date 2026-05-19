/** captureImage 的单测：Taro.chooseMedia 参数 + 返回值映射 + 用户取消透传。 */
import Taro from '@tarojs/taro';
import { captureImage } from '../../src/hooks/useImageCapture';

const mockedChooseMedia = Taro.chooseMedia as unknown as jest.Mock;

describe('hooks/useImageCapture.captureImage', () => {
  beforeEach(() => {
    mockedChooseMedia.mockReset();
  });

  it('returns first image meta from Taro.chooseMedia', async () => {
    mockedChooseMedia.mockResolvedValueOnce({
      tempFiles: [
        {
          tempFilePath: '/tmp/a.jpg',
          size: 12345,
          fileType: 'image',
        },
      ],
    });

    const result = await captureImage();

    expect(result).toEqual({
      tempFilePath: '/tmp/a.jpg',
      size: 12345,
      fileType: 'image',
    });
    expect(mockedChooseMedia).toHaveBeenCalledTimes(1);
    expect(mockedChooseMedia).toHaveBeenCalledWith({
      count: 1,
      mediaType: ['image'],
      sourceType: ['camera', 'album'],
      sizeType: ['original'],
    });
  });

  it('captureImage propagates rejection (user cancel)', async () => {
    mockedChooseMedia.mockRejectedValueOnce({
      errMsg: 'chooseMedia:fail cancel',
    });

    await expect(captureImage()).rejects.toMatchObject({
      errMsg: 'chooseMedia:fail cancel',
    });
  });
});

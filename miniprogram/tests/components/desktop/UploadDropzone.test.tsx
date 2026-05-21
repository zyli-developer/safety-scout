/**
 * 单元测试：UploadDropzone (clean-minimal).
 *
 * 验收要点：
 * - idle 默认渲染中文 + sublabel 提示
 * - 点击触发隐藏 <input type="file"> 的 click()
 * - 选择文件触发 onSelect(file)
 * - 拖入文件触发 onSelect(file) + 阻止默认浏览器行为
 * - dragenter / dragleave 切换 data-hover
 * - uploading 时不响应 click / drop / 键盘 + aria-busy=true + tabindex=-1
 */
import { fireEvent, render, screen } from '@testing-library/react';

import { UploadDropzone } from '../../../src/components/desktop/UploadDropzone';

function makeJpegFile(name = 'photo.jpg'): File {
  return new File([new Uint8Array([0xff, 0xd8, 0xff])], name, { type: 'image/jpeg' });
}

describe('UploadDropzone', () => {
  it('renders default idle copy', () => {
    render(<UploadDropzone onSelect={() => undefined} />);
    expect(screen.getByText(/拖拽图片/)).toBeInTheDocument();
    expect(screen.getByText(/点击选择文件/)).toBeInTheDocument();
    expect(screen.getByText('选择文件')).toBeInTheDocument();
  });

  it('calls onSelect when file picked via input change', () => {
    const fn = jest.fn();
    const { container } = render(<UploadDropzone onSelect={fn} />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    expect(input).not.toBeNull();

    const file = makeJpegFile();
    fireEvent.change(input, { target: { files: [file] } });
    expect(fn).toHaveBeenCalledWith(file);
  });

  it('triggers hidden input click when dropzone is clicked', () => {
    const fn = jest.fn();
    const { container } = render(<UploadDropzone onSelect={fn} />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const clickSpy = jest.spyOn(input, 'click').mockImplementation(() => undefined);
    fireEvent.click(screen.getByRole('button'));
    expect(clickSpy).toHaveBeenCalledTimes(1);
  });

  it('calls onSelect when file is dropped', () => {
    const fn = jest.fn();
    render(<UploadDropzone onSelect={fn} />);
    const zone = screen.getByRole('button');
    const file = makeJpegFile();

    fireEvent.drop(zone, {
      dataTransfer: { files: [file], items: [{ kind: 'file', type: file.type, getAsFile: () => file }] },
    });
    expect(fn).toHaveBeenCalledWith(file);
  });

  it('sets aria-busy when uploading and ignores interactions', () => {
    const fn = jest.fn();
    const { container } = render(<UploadDropzone onSelect={fn} uploading />);
    const zone = screen.getByRole('button');
    expect(zone).toHaveAttribute('aria-busy', 'true');

    fireEvent.click(zone);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const clickSpy = jest.spyOn(input, 'click').mockImplementation(() => undefined);
    expect(clickSpy).not.toHaveBeenCalled();

    fireEvent.drop(zone, { dataTransfer: { files: [makeJpegFile()] } });
    expect(fn).not.toHaveBeenCalled();
  });

  it('toggles data-hover on dragenter/dragleave', () => {
    render(<UploadDropzone onSelect={() => undefined} />);
    const zone = screen.getByRole('button');
    fireEvent.dragEnter(zone);
    expect(zone).toHaveAttribute('data-hover', 'true');
    fireEvent.dragLeave(zone);
    expect(zone).toHaveAttribute('data-hover', 'false');
  });

  it('activates via Enter key (keyboard a11y)', () => {
    const fn = jest.fn();
    const { container } = render(<UploadDropzone onSelect={fn} />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const clickSpy = jest.spyOn(input, 'click').mockImplementation(() => undefined);

    const zone = screen.getByRole('button');
    expect(zone).toHaveAttribute('tabindex', '0');

    fireEvent.keyDown(zone, { key: 'Enter' });
    expect(clickSpy).toHaveBeenCalledTimes(1);
  });

  it('activates via Space key and is not focusable when uploading', () => {
    const fn = jest.fn();
    const { container, rerender } = render(<UploadDropzone onSelect={fn} />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const clickSpy = jest.spyOn(input, 'click').mockImplementation(() => undefined);

    fireEvent.keyDown(screen.getByRole('button'), { key: ' ' });
    expect(clickSpy).toHaveBeenCalledTimes(1);

    rerender(<UploadDropzone onSelect={fn} uploading />);
    expect(screen.getByRole('button')).toHaveAttribute('tabindex', '-1');
    clickSpy.mockClear();
    fireEvent.keyDown(screen.getByRole('button'), { key: 'Enter' });
    expect(clickSpy).not.toHaveBeenCalled();
  });
});

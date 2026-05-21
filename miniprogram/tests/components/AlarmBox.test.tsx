import { render, screen } from '@testing-library/react';
import { AlarmBox } from '../../src/components/AlarmBox';

describe('AlarmBox', () => {
  it('renders default lead label + body text', () => {
    render(<AlarmBox>清理临边洞口</AlarmBox>);
    expect(screen.getByText(/立即处置/)).toBeInTheDocument();
    expect(screen.getByText('清理临边洞口')).toBeInTheDocument();
  });

  it('accepts custom leadLabel', () => {
    render(<AlarmBox leadLabel="紧急">检查防护</AlarmBox>);
    expect(screen.getByText(/紧急/)).toBeInTheDocument();
  });
});

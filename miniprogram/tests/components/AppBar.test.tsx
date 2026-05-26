import { fireEvent, render, screen } from '@testing-library/react';
import { AppBar } from '../../src/components/AppBar';

describe('AppBar', () => {
  it('renders title', () => {
    render(<AppBar title="巡检报告" />);
    expect(screen.getByText('巡检报告')).toBeInTheDocument();
  });

  it('shows back button by default with aria-label 返回', () => {
    render(<AppBar title="X" />);
    expect(screen.getByLabelText('返回')).toBeInTheDocument();
  });

  it('hides back button when backless', () => {
    render(<AppBar title="X" backless />);
    expect(screen.queryByLabelText('返回')).not.toBeInTheDocument();
  });

  it('fires onBack when back tapped', () => {
    const onBack = jest.fn();
    render(<AppBar title="X" onBack={onBack} />);
    fireEvent.click(screen.getByLabelText('返回'));
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it('renders right slot', () => {
    render(<AppBar title="X" right={<span>分享</span>} />);
    expect(screen.getByText('分享')).toBeInTheDocument();
  });
});

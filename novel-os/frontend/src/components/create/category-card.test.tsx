import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CategoryCard } from './category-card'

const category = {
  name: '玄幻',
  genre: '东方玄幻',
  tags: ['热血', '升级', '废柴流'],
}

describe('CategoryCard', () => {
  it('renders category name', () => {
    render(<CategoryCard {...category} selected={false} onClick={vi.fn()} />)
    expect(screen.getByText('玄幻')).toBeInTheDocument()
  })

  it('renders genre when different from name', () => {
    render(<CategoryCard {...category} selected={false} onClick={vi.fn()} />)
    expect(screen.getByText('东方玄幻')).toBeInTheDocument()
  })

  it('does not render genre when same as name', () => {
    render(<CategoryCard name="玄幻" selected={false} onClick={vi.fn()} />)
    expect(screen.getAllByText('玄幻')).toHaveLength(1)
  })

  it('renders up to 3 tags', () => {
    render(<CategoryCard {...category} selected={false} onClick={vi.fn()} />)
    expect(screen.getByText('热血')).toBeInTheDocument()
    expect(screen.getByText('升级')).toBeInTheDocument()
    expect(screen.getByText('废柴流')).toBeInTheDocument()
  })

  it('calls onClick when clicked', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    render(<CategoryCard {...category} selected={false} onClick={onClick} />)

    await user.click(screen.getByText('玄幻'))
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('shows check icon when selected', () => {
    const { container } = render(<CategoryCard {...category} selected={true} onClick={vi.fn()} />)
    expect(container.querySelector('svg')).toBeInTheDocument()
  })
})

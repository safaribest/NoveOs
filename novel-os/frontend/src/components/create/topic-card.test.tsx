import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TopicCard } from './topic-card'

const topic = {
  id: '1',
  title: '逆天改命',
  hook: '一个被判定为废物的少年，意外获得上古传承',
  slap_points: ['打脸族长', '碾压天才', '逆袭宗门'],
  target_reader: '喜欢热血逆袭的读者',
  risks: ['节奏拖沓', '反派降智'],
  why_now: '复仇逆袭题材持续火热',
}

describe('TopicCard', () => {
  it('renders topic title and hook', () => {
    render(<TopicCard topic={topic} onSelect={vi.fn()} />)
    expect(screen.getByText('逆天改命')).toBeInTheDocument()
    expect(screen.getByText(topic.hook)).toBeInTheDocument()
  })

  it('renders recommended badge', () => {
    render(<TopicCard topic={topic} onSelect={vi.fn()} isRecommended />)
    expect(screen.getByText('推荐')).toBeInTheDocument()
  })

  it('renders slap points and target reader', () => {
    render(<TopicCard topic={topic} onSelect={vi.fn()} />)
    expect(screen.getByText('打脸族长')).toBeInTheDocument()
    expect(screen.getByText('喜欢热血逆袭的读者')).toBeInTheDocument()
  })

  it('renders risks', () => {
    render(<TopicCard topic={topic} onSelect={vi.fn()} />)
    expect(screen.getByText('节奏拖沓')).toBeInTheDocument()
    expect(screen.getByText('反派降智')).toBeInTheDocument()
  })

  it('calls onSelect when button clicked', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    render(<TopicCard topic={topic} onSelect={onSelect} />)

    await user.click(screen.getByRole('button', { name: /选这个/i }))
    expect(onSelect).toHaveBeenCalledTimes(1)
  })
})

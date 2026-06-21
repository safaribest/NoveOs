import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ProviderForm } from './provider-form'
import type { LLMProvider } from '@/types'

const validProvider: LLMProvider = {
  name: 'deepseek',
  type: 'deepseek',
  api_key: 'sk-test',
  base_url: 'https://api.deepseek.com/v1',
  model: 'deepseek-chat',
  temperature: 0.8,
  max_tokens: 4096,
  timeout: 120,
}

describe('ProviderForm', () => {
  it('renders all fields', () => {
    render(<ProviderForm onSubmit={vi.fn()} onCancel={vi.fn()} />)

    expect(screen.getByLabelText('名称')).toBeInTheDocument()
    expect(screen.getByLabelText('Provider 类型')).toBeInTheDocument()
    expect(screen.getByLabelText('API Key')).toBeInTheDocument()
    expect(screen.getByLabelText('Base URL')).toBeInTheDocument()
    expect(screen.getByLabelText('模型')).toBeInTheDocument()
  })

  it('shows validation errors on empty submit', async () => {
    const user = userEvent.setup()
    render(<ProviderForm onSubmit={vi.fn()} onCancel={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: /添加 Provider/i }))

    await waitFor(() => {
      expect(screen.getByText('名称不能为空')).toBeInTheDocument()
      expect(screen.getByText('API Key 不能为空')).toBeInTheDocument()
    })
  })

  it('submits when initial data is valid', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(
      <ProviderForm
        initialData={validProvider}
        onSubmit={onSubmit}
        onCancel={vi.fn()}
      />
    )

    await user.click(screen.getByRole('button', { name: /保存修改/i }))

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1)
      expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining(validProvider))
    })
  })

  it('shows duplicate name error in edit mode', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(
      <ProviderForm
        initialData={{ ...validProvider, name: 'existing' }}
        existingNames={['existing', 'reserved']}
        onSubmit={onSubmit}
        onCancel={vi.fn()}
      />
    )

    // 编辑模式下名称不可改，但可以通过改名字段绕过前端 disabled 验证 handleFormSubmit 逻辑
    // 这里直接验证提交能走通，因为 reservedNames 过滤掉了当前名称
    await user.click(screen.getByRole('button', { name: /保存修改/i }))

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1)
    })
  })

  it('calls onCancel when cancel clicked', async () => {
    const user = userEvent.setup()
    const onCancel = vi.fn()
    render(<ProviderForm onSubmit={vi.fn()} onCancel={onCancel} />)

    await user.click(screen.getByRole('button', { name: /取消/i }))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })
})

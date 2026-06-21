import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { LLMPage } from './llm-page'
import * as settingsApi from '@/api/settings'
import { renderWithProviders } from '@/test/test-utils'

vi.mock('@/api/settings', () => ({
  getLLMSettings: vi.fn(),
  updateLLMSettings: vi.fn(),
  testLLMConnection: vi.fn(),
  getAgentProviders: vi.fn(() => Promise.resolve({})),
  updateAgentProviders: vi.fn(() => Promise.resolve({})),
  providerTypeOptions: vi.fn(() => [
    { value: 'deepseek', label: 'DeepSeek' },
    { value: 'openai', label: 'OpenAI' },
    { value: 'kimi', label: 'Moonshot (Kimi)' },
    { value: 'custom', label: '自定义 OpenAI-compatible' },
  ]),
  getProviderDefaults: vi.fn(() => ({ base_url: '', model: '' })),
}))

describe('LLMPage', () => {
  afterEach(() => {
    vi.resetAllMocks()
  })

  it('renders loading state', () => {
    vi.mocked(settingsApi.getLLMSettings).mockReturnValue(new Promise(() => {}))
    renderWithProviders(<LLMPage />)

    expect(screen.getAllByText('Provider 列表').length).toBeGreaterThanOrEqual(1)
    expect(document.querySelectorAll('.animate-pulse').length).toBeGreaterThan(0)
  })

  it('renders empty state', async () => {
    vi.mocked(settingsApi.getLLMSettings).mockResolvedValueOnce({
      default_provider: '',
      providers: {},
    })
    renderWithProviders(<LLMPage />)

    await waitFor(() => {
      expect(screen.getByText('还没有配置任何 LLM Provider')).toBeInTheDocument()
    })
  })

  it('renders provider list', async () => {
    vi.mocked(settingsApi.getLLMSettings).mockResolvedValueOnce({
      default_provider: 'deepseek',
      providers: {
        deepseek: {
          name: 'deepseek',
          type: 'deepseek',
          api_key: 'sk-***',
          base_url: 'https://api.deepseek.com/v1',
          model: 'deepseek-chat',
          temperature: 0.8,
          max_tokens: 4096,
          timeout: 120,
        },
      },
    })
    renderWithProviders(<LLMPage />)

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'deepseek' })).toBeInTheDocument()
      expect(screen.getByText(/当前默认 Provider：deepseek/i)).toBeInTheDocument()
    })
  })

  it('opens and closes provider form', async () => {
    const user = userEvent.setup()
    vi.mocked(settingsApi.getLLMSettings).mockResolvedValueOnce({
      default_provider: '',
      providers: {},
    })

    renderWithProviders(<LLMPage />)

    await waitFor(() => {
      expect(screen.getByText('还没有配置任何 LLM Provider')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /添加 Provider/i }))

    await waitFor(() => {
      expect(screen.getByLabelText('名称')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /取消/i })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /取消/i }))

    await waitFor(() => {
      expect(screen.queryByLabelText('名称')).not.toBeInTheDocument()
      expect(screen.getByText('还没有配置任何 LLM Provider')).toBeInTheDocument()
    })
  })
})

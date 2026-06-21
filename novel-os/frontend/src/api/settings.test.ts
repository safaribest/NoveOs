import { getLLMSettings, updateLLMSettings, testLLMConnection, providerTypeOptions, getProviderDefaults } from './settings'
import { get, put, post } from '@/lib/api'

vi.mock('@/lib/api')

describe('settings API', () => {
  afterEach(() => {
    vi.resetAllMocks()
  })

  it('getLLMSettings calls correct endpoint', async () => {
    const settings = { default_provider: 'deepseek', providers: {} }
    vi.mocked(get).mockResolvedValueOnce(settings)

    const result = await getLLMSettings()
    expect(get).toHaveBeenCalledWith('/settings/llm')
    expect(result).toEqual(settings)
  })

  it('updateLLMSettings calls correct endpoint', async () => {
    const settings = { default_provider: 'deepseek', providers: {} }
    vi.mocked(put).mockResolvedValueOnce(settings)

    const result = await updateLLMSettings(settings)
    expect(put).toHaveBeenCalledWith('/settings/llm', settings)
    expect(result).toEqual(settings)
  })

  it('testLLMConnection calls correct endpoint', async () => {
    const result = { success: true, message: 'ok' }
    vi.mocked(post).mockResolvedValueOnce(result)

    const response = await testLLMConnection('deepseek')
    expect(post).toHaveBeenCalledWith('/settings/llm/test', { provider_name: 'deepseek' })
    expect(response).toEqual(result)
  })
})

describe('providerTypeOptions', () => {
  it('returns all provider types', () => {
    const options = providerTypeOptions()
    expect(options).toHaveLength(4)
    expect(options.map((o) => o.value)).toEqual(['deepseek', 'openai', 'kimi', 'custom'])
  })
})

describe('getProviderDefaults', () => {
  it('returns deepseek defaults', () => {
    expect(getProviderDefaults('deepseek')).toEqual({
      base_url: 'https://api.deepseek.com/v1',
      model: 'deepseek-chat',
    })
  })

  it('returns openai defaults', () => {
    expect(getProviderDefaults('openai')).toEqual({
      base_url: 'https://api.openai.com/v1',
      model: 'gpt-4o-mini',
    })
  })

  it('returns kimi defaults', () => {
    expect(getProviderDefaults('kimi')).toEqual({
      base_url: 'https://api.moonshot.cn/v1',
      model: 'kimi-latest',
    })
  })

  it('returns empty defaults for unknown type', () => {
    expect(getProviderDefaults('unknown')).toEqual({ base_url: '', model: '' })
  })
})

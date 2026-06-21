import { type ReactElement, type ReactNode } from 'react'
import { render, type RenderOptions } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '@/components/theme-provider'

export function renderWithProviders(
  ui: ReactElement,
  options: RenderOptions & { initialRoute?: string } = {}
) {
  const { initialRoute, ...renderOptions } = options
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return render(ui, {
    wrapper: ({ children }: { children: ReactNode }) => (
      <ThemeProvider defaultTheme="light">
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={[initialRoute ?? '/']}>
            {children}
          </MemoryRouter>
        </QueryClientProvider>
      </ThemeProvider>
    ),
    ...renderOptions,
  })
}

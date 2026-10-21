import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { axe } from 'vitest-axe'

import { FormTimezoneSelect } from './FormTimezoneSelect'

describe('FormTimezoneSelect', () => {
  it('renders the selected timezone in the typeahead input', () => {
    render(<FormTimezoneSelect id="tz-select" value="America/New_York" onChange={vi.fn()} ariaLabel="Time zone" />)

    expect(screen.getByRole('textbox', { name: 'Time zone' })).toHaveValue('America/New_York')
    expect(screen.getByRole('button', { name: 'Clear time zone' })).toBeInTheDocument()
  })

  it('has no accessibility violations', async () => {
    const { container } = render(
      <FormTimezoneSelect id="tz-select" value="" onChange={vi.fn()} ariaLabel="Time zone" />
    )

    expect(await axe(container)).toHaveNoViolations()
  })
})

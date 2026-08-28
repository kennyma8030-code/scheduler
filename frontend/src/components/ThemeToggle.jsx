import { useState } from 'react'

const savedTheme = localStorage.getItem('theme') ?? 'light'
document.documentElement.setAttribute('data-theme', savedTheme)

export default function ThemeToggle() {
  const [dark, setDark] = useState(
    document.documentElement.getAttribute('data-theme') === 'dark'
  )
  function toggle() {
    const next = !dark
    setDark(next)
    document.documentElement.setAttribute('data-theme', next ? 'dark' : 'light')
    localStorage.setItem('theme', next ? 'dark' : 'light')
  }
  return (
    <button className="theme-toggle" onClick={toggle} title={dark ? 'Light mode' : 'Dark mode'}>
      {dark ? '☀' : '☽'}
    </button>
  )
}

// Single place the backend URL lives. Explicitly 127.0.0.1 rather than
// localhost: on Windows with WSL or Docker running, localhost resolves to ::1
// first, where their port proxies answer instead of uvicorn.
const API_BASE = 'http://127.0.0.1:8000/api'

async function request(path, options) {
  const res = await fetch(`${API_BASE}${path}`, options)
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail ?? detail } catch { /* keep statusText */ }
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  terms: () => request('/terms'),
  subjects: (termKey) => request(`/subjects?term_key=${termKey}`),
  coreCodes: (termKey) => request(`/core-codes?term_key=${termKey}`),
  // `signal` lets the caller cancel a superseded request — see CourseSearch.
  searchCourses: (termKey, q, { extra = '', signal } = {}) =>
    request(
      `/courses/search?term_key=${termKey}&q=${encodeURIComponent(q)}${extra}`,
      { signal },
    ),
  courseDetail: (termKey, courseString, supplement = '') =>
    request(`/courses/${termKey}/${encodeURIComponent(courseString)}?supplement=${encodeURIComponent(supplement)}`),
  openStatus: (termKey) => request(`/open-status?term_key=${termKey}`),
  generate: (body) =>
    request('/schedule/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  save: (body) =>
    request('/schedule/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  saved: () => request('/schedule/saved'),
  loadSaved: (id) => request(`/schedule/saved/${id}`),
}

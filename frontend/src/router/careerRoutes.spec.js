import { describe, expect, it } from 'vitest'
import { router } from './index'

describe('career workspace routes', () => {
  it.each([
    ['/resumes', 'career-resumes', 'resumes'],
    ['/jobs', 'career-jobs', 'jobs'],
    ['/applications', 'career-applications', 'applications'],
    ['/interviews', 'career-interviews', 'interviews'],
    ['/reports', 'career-reports', 'reports'],
    ['/profile/skills', 'career-skills', 'skills']
  ])('resolves %s inside the authenticated workspace shell', (path, name, resource) => {
    const route = router.resolve(path)

    expect(route.name).toBe(name)
    expect(route.meta).toMatchObject({
      requiresAuth: true,
      layout: 'workspace',
      workspaceSection: 'career'
    })
    expect(route.matched.at(-1)?.props?.default).toEqual({ resource })
  })
})

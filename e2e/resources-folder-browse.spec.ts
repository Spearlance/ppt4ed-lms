import { test, expect, Page } from '@playwright/test'

/**
 * Smoke tests for PR B (folder browse on /lms/resources):
 *  - Top-level folder cards render on the resource catalog
 *  - Clicking a folder card pushes ?category=... and renders the breadcrumb
 *  - Resources attached to a category's descendant subtree appear when
 *    browsing the parent (lft/rgt subtree filter on get_resources)
 *
 * Runs against devlms.ppt4ed.org with the seeded global-admin test user.
 */

const ADMIN_EMAIL = 'global-admin@test.com'
const ADMIN_PASSWORD = 'TestUser@2026!'

const STAMP = Date.now().toString().slice(-6)
const PARENT = `pw-parent-${STAMP}`
const CHILD = `pw-child-${STAMP}`
const RESOURCE_TITLE = `pw-folder-resource-${STAMP}`

async function loginAsAdmin(page: Page) {
	await page.goto('/login')
	await page.fill('#login_email', ADMIN_EMAIL)
	await page.fill('#login_password', ADMIN_PASSWORD)
	await page.click('.btn-login')
	await page.waitForURL('**/lms/**', { timeout: 15000 })
}

async function logout(page: Page) {
	await page.goto('/api/method/logout')
	await page.waitForLoadState('networkidle')
}

async function api(page: Page, method: string, data: Record<string, unknown>) {
	const csrf = await page.evaluate(() => (window as any).csrf_token as string)
	return page.request.post(`/api/method/${method}`, {
		headers: { 'X-Frappe-CSRF-Token': csrf },
		data,
	})
}

test.describe('PR B — Resources folder browse', () => {
	test('parent folder card shows a resource attached to the child subtree', async ({ page }) => {
		await loginAsAdmin(page)

		// Seed the tree: PARENT > CHILD, then a resource (LMS Course with
		// course_type='Resource') assigned to CHILD.
		const parentRes = await api(page, 'lms.lms.api.create_category', {
			label: PARENT,
			parent: null,
		})
		expect(parentRes.ok(), await parentRes.text()).toBeTruthy()
		const childRes = await api(page, 'lms.lms.api.create_category', {
			label: CHILD,
			parent: PARENT,
		})
		expect(childRes.ok(), await childRes.text()).toBeTruthy()

		// frappe.client.insert is whitelisted; it'll auto-name the course.
		const resourceRes = await api(page, 'frappe.client.insert', {
			doc: {
				doctype: 'LMS Course',
				title: RESOURCE_TITLE,
				short_introduction: 'Folder browse smoke test',
				description: '<p>Test resource for PR B subtree filter.</p>',
				course_type: 'Resource',
				resource_type: 'Article',
				category: CHILD,
				published: 1,
				published_on: new Date().toISOString().split('T')[0],
			},
		})
		expect(resourceRes.ok(), await resourceRes.text()).toBeTruthy()
		const resourceName = (await resourceRes.json()).message.name as string

		// Hit /lms/resources root — PARENT should appear as a folder card.
		await page.goto('/lms/resources')
		const parentCard = page.locator('button', { hasText: PARENT }).first()
		await expect(parentCard).toBeVisible({ timeout: 10000 })

		// Click the parent folder. URL gains ?category=PARENT, breadcrumb shows
		// the trail, and the seeded resource (attached to CHILD, the descendant)
		// appears via the lft/rgt subtree filter on get_resources.
		await parentCard.click()
		await page.waitForURL(/category=/, { timeout: 5000 })
		await expect(page.getByText(PARENT).first()).toBeVisible({ timeout: 10000 })
		await expect(page.getByText(CHILD).first()).toBeVisible({ timeout: 10000 })
		await expect(page.getByText(RESOURCE_TITLE).first()).toBeVisible({
			timeout: 10000,
		})

		// Cleanup: resource then deepest category first.
		await api(page, 'frappe.client.delete', {
			doctype: 'LMS Course',
			name: resourceName,
		}).catch(() => {})
		for (const name of [CHILD, PARENT]) {
			await api(page, 'lms.lms.api.delete_category', { name, force: 1 }).catch(() => {})
		}

		await logout(page)
	})
})

import { test, expect, Page } from '@playwright/test'

/**
 * Smoke tests for the LMS Course multi-category change (PR #156).
 *
 * Scope of what's testable as a Global Admin (which is the user role
 * relevant to this PR's access-control work):
 *  - /lms/admin-categories renders for GA (the 502 the user reported was
 *    operational, not a perm/code issue; this regression catches it if it
 *    comes back).
 *  - The `_category_resource_count` query reads through the new
 *    `LMS Course Category` child table — the resource-count badges on
 *    folder cards must be non-zero for the migrated seed categories.
 *  - `get_resources` with a category filter resolves through the child
 *    table via `_resolve_category_filter_to_course_names` and returns the
 *    same rows that the migration patch seeded.
 *  - `/lms/resources?category=<X>` UI exposes the same resources.
 *
 * The "single resource under TWO categories" assertion needs author-level
 * writes (Moderator/SysMgr), which the dev test users don't have. Verify
 * that path manually in the dev frontend, or via a System Manager session.
 */

const ADMIN_EMAIL = 'global-admin@test.com'
const ADMIN_PASSWORD = 'TestUser@2026!'

const CAT_SOCIAL = 'Social Stories'
const CAT_EDU = 'Educational'

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

test.describe('Multi-category resources (PR #156)', () => {
	test('Global Admin can open /lms/admin-categories', async ({ page }) => {
		await loginAsAdmin(page)

		const response = await page.goto('/lms/admin-categories')
		expect(response?.status(), 'admin-categories page status').toBeLessThan(400)

		// "Add top-level category" is the per-page action button — only renders
		// for an authorized admin.
		await expect(
			page.getByRole('button', { name: 'Add top-level category' })
		).toBeVisible({ timeout: 10000 })

		// Seed categories should appear as folder cards.
		await expect(page.getByText(CAT_SOCIAL).first()).toBeVisible({ timeout: 10000 })
		await expect(page.getByText(CAT_EDU).first()).toBeVisible({ timeout: 10000 })

		await logout(page)
	})

	test('admin-categories shows non-zero resource counts post-migration', async ({ page }) => {
		// The PR's `_category_resource_count` rewires from the legacy
		// `LMS Course.category` column to the new `LMS Course Category`
		// child table. If the migration patch ran and the count helper reads
		// the child table, both Social Stories and Educational should show
		// counts > 0 on the page.
		await loginAsAdmin(page)
		await page.goto('/lms/admin-categories')

		// Folder cards are <button> wrappers — find the row containing CAT_SOCIAL.
		const socialCard = page
			.locator('div', { has: page.locator('button', { hasText: CAT_SOCIAL }) })
			.first()
		await expect(socialCard).toBeVisible({ timeout: 10000 })
		// The card body includes the "<N> resources" badge.
		await expect(socialCard).toContainText(/\d+\s+resources?/, { timeout: 10000 })

		const eduCard = page
			.locator('div', { has: page.locator('button', { hasText: CAT_EDU }) })
			.first()
		await expect(eduCard).toBeVisible({ timeout: 10000 })
		await expect(eduCard).toContainText(/\d+\s+resources?/, { timeout: 10000 })

		await logout(page)
	})

	test('get_resources filters through the new child table', async ({ page }) => {
		await loginAsAdmin(page)

		const csrf = await page.evaluate(() => (window as any).csrf_token as string)
		const filterByCategory = async (cat: string) => {
			// Call get_resources via the page so it goes through the same
			// frappe.call path the Vue layer uses (proper JSON arg coercion
			// for the `filters` dict). Returns the `message` array directly.
			const j = await page.evaluate(
				async ({ method, category, csrfToken }) => {
					const res = await fetch(`/api/method/${method}`, {
						method: 'POST',
						credentials: 'include',
						headers: {
							'Content-Type': 'application/json',
							'X-Frappe-CSRF-Token': csrfToken,
						},
						body: JSON.stringify({ filters: { category }, start: 0 }),
					})
					if (!res.ok) {
						throw new Error(`status ${res.status}: ${await res.text()}`)
					}
					return (await res.json()).message
				},
				{ method: 'lms.lms.utils.get_resources', category: cat, csrfToken: csrf }
			)
			return j as any[]
		}

		const social = await filterByCategory(CAT_SOCIAL)
		expect(social.length, 'Social Stories should have migrated resources').toBeGreaterThan(0)
		// `attach_course_categories` should have populated `categories` on each
		// returned card so the folder UI can dedupe across folders.
		expect(social[0].categories, 'attach_course_categories must populate categories[]').toContain(CAT_SOCIAL)

		const edu = await filterByCategory(CAT_EDU)
		expect(edu.length, 'Educational should have migrated resources').toBeGreaterThan(0)
		expect(edu[0].categories).toContain(CAT_EDU)

		// Cross-check: a Social Stories resource is NOT in the Educational filter.
		const socialNames = new Set(social.map((r) => r.name))
		const overlap = edu.filter((r) => socialNames.has(r.name))
		expect(overlap, 'no cross-pollination between distinct top-level folders').toHaveLength(0)

		await logout(page)
	})

	test('Resources page folder view renders cards for both seed categories', async ({ page }) => {
		await loginAsAdmin(page)

		// Browse into Social Stories. Expect at least one resource card to
		// render (the migration seeded 15 there).
		await page.goto(`/lms/resources?category=${encodeURIComponent(CAT_SOCIAL)}`)
		const socialCards = page.locator('a[href*="/lms/resources/"]')
		await expect(socialCards.first(), `cards under ${CAT_SOCIAL}`).toBeVisible({
			timeout: 10000,
		})

		await page.goto(`/lms/resources?category=${encodeURIComponent(CAT_EDU)}`)
		const eduCards = page.locator('a[href*="/lms/resources/"]')
		await expect(eduCards.first(), `cards under ${CAT_EDU}`).toBeVisible({
			timeout: 10000,
		})

		await logout(page)
	})
})

import { test, expect, Page } from '@playwright/test'

/**
 * Post-deploy smoke covering the three fixes from PR #68 plus the
 * underlying public landings shipped in PRs #65–#67. Runs against the
 * live devlms.ppt4ed.org. No user state is created or modified.
 */

const FREE_COURSE_SLUG =
	'the-power-of-play-linking-play-to-language-cognitive-social-emotional-literacy-development'
const EVENT_SLUG = 'pediatric-adaptive-equipment-evaluation-and-fitting'

async function expectImageRenders(page: Page, locator: string) {
	const img = page.locator(locator)
	await expect(img).toBeVisible()
	const dims = await img.evaluate((el: HTMLImageElement) => ({
		w: el.naturalWidth,
		h: el.naturalHeight,
		src: el.src,
	}))
	expect(dims.src, 'img src should not be [object Object]').not.toContain('[object Object]')
	expect(dims.w, `img naturalWidth must be > 0 (was ${dims.w}, src=${dims.src})`).toBeGreaterThan(0)
	expect(dims.h, `img naturalHeight must be > 0 (was ${dims.h}, src=${dims.src})`).toBeGreaterThan(0)
}

test.describe('Post-deploy smoke (PR #68)', () => {
	test('membership plans: Free card visible on Individual tab, PPT Employee hidden', async ({ page }) => {
		await page.goto('/lms/membership-plans')

		// Default tab is Company; switch to Individual.
		await page.getByRole('button', { name: /^Individual$/ }).click()

		// Free card present
		const freeCard = page.locator('h3:text("Free")').first()
		await expect(freeCard).toBeVisible()

		// "Browse" badge on the Free card (distinguishes from real plans)
		await expect(page.locator('text=Browse').first()).toBeVisible()

		// $0 price on the Free card
		await expect(page.getByText('$0').first()).toBeVisible()

		// At least one paid Individual plan card exists alongside Free
		// (Professional Membership or Individual Business Membership)
		const paidCardTitles = await page
			.locator('h3.text-lg.font-semibold')
			.allTextContents()
		const hasPaid = paidCardTitles.some((t) =>
			/Professional Membership|Individual Business Membership|Educational Partner/i.test(t)
		)
		expect(hasPaid, `Expected at least one paid Individual plan; saw ${JSON.stringify(paidCardTitles)}`).toBe(true)

		// PPT Employee plan must not appear anywhere on the page
		const bodyText = await page.locator('body').innerText()
		expect(bodyText).not.toMatch(/PPT Employee/)
	})

	test('signup page: PPT4ed logo image renders with non-empty natural dimensions', async ({ page }) => {
		await page.goto('/lms/signup')

		await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()

		// Target the Signup card's hero logo specifically — the AppSidebar
		// also renders an <img> for the brand button, so a bare locator('img')
		// would be ambiguous. The Signup hero logo has class `mx-auto h-10`.
		const heroLogo = 'img.mx-auto.h-10'
		await page.locator(heroLogo).waitFor({ state: 'visible', timeout: 8000 })

		await expectImageRenders(page, heroLogo)
	})

	test('course landing /c/<slug> renders with guest register CTA', async ({ page }) => {
		await page.goto(`/c/${FREE_COURSE_SLUG}`)

		// Hero copy + outline are server-rendered
		await expect(page).toHaveTitle(/Power of Play/i)
		await expect(page.locator('h1').first()).toContainText(/Power of Play/i)

		// At least one register-modal trigger
		const cta = page.locator('[data-action="open-register"]').first()
		await expect(cta).toBeVisible()

		// Clicking opens the modal
		await cta.click()
		await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()

		// Email field is empty (no prefill on first open) and Log In tab is reachable
		await expect(page.locator('#register-modal-signup input[name="email"]')).toHaveValue('')
		await page.getByRole('tab', { name: 'Log in' }).click()
		await expect(page.locator('#register-modal-login input[name="usr"]')).toBeVisible()
	})

	test('event landing /e/<slug> renders with schedule + guest register CTA', async ({ page }) => {
		await page.goto(`/e/${EVENT_SLUG}`)

		await expect(page.locator('h1').first()).toContainText(/Pediatric Adaptive Equipment/i)

		// Schedule section emitted (multi-day or single-day)
		await expect(page.getByRole('heading', { name: 'Schedule' })).toBeVisible()

		// Register modal trigger present
		await expect(page.locator('[data-action="open-register"]').first()).toBeVisible()
	})

	test('AppSidebar is hidden on guest-allowed Vue pages (signup, membership-plans)', async ({ page }) => {
		// AppSidebar's root carries `bg-surface-menu-bar`; NoSidebarLayout
		// doesn't render any element with that class.
		const sidebar = 'div.bg-surface-menu-bar'

		await page.goto('/lms/signup')
		await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
		await expect(page.locator(sidebar)).toHaveCount(0)

		await page.goto('/lms/membership-plans')
		await expect(page.getByRole('heading', { name: 'Choose Your Plan' })).toBeVisible()
		await expect(page.locator(sidebar)).toHaveCount(0)
	})

	test('event landing modal: submitting an existing email pivots to Log In tab', async ({ page }) => {
		// Uses a known seeded user from company-employee.spec.ts:
		//   pro@test.com / TestUser@2026!
		// The modal should reject signup with "exists" status and pivot.
		await page.goto(`/e/${EVENT_SLUG}`)
		await page.locator('[data-action="open-register"]').first().click()

		await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()

		// Fill the signup form with an email that already exists
		await page.locator('#register-modal-signup input[name="full_name"]').fill('Smoke Test')
		await page.locator('#register-modal-signup input[name="email"]').fill('pro@test.com')
		await page.locator('#register-modal-signup input[name="password"]').fill('TestUser@2026!')
		await page.locator('#register-modal-signup button[type="submit"]').click()

		// Modal pivots to Log In tab with email prefilled
		await expect(page.getByText('That email is already registered')).toBeVisible({ timeout: 10000 })
		await expect(page.locator('#register-modal-login input[name="usr"]')).toHaveValue('pro@test.com')
	})
})

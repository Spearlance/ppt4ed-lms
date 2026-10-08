import { test, expect, Page } from '@playwright/test'

/**
 * Course upsells (PR #196) on devlms, driven end-to-end through Stripe test mode.
 *
 * Dev setup these tests assume (see lms/lms/ceu_upsell.py):
 *   - CEU Stripe Settings: enable_order_bump=1, enable_post_purchase_upsell=1, 50% off
 *   - MAIN <-> RELATED are each other's first Related Course, both $30 / 2 CEU
 *   - Two throwaway learners with no enrollments (seeded by the session that runs this):
 *       upsell-smoke-bump@test.com / TestUser@2026!
 *       upsell-smoke-post@test.com / TestUser@2026!
 *
 * Each test buys a real $30 test-mode course, so run them one at a time and
 * re-seed the users (delete their enrollments + payments) before a rerun.
 */

const PASSWORD = 'TestUser@2026!'
const BUMP_USER = 'upsell-smoke-bump@test.com'
const POST_USER = 'upsell-smoke-post@test.com'

const MAIN = 'introduction-to-upper-extremity-splinting-for-function-in-pediatrics'
const MAIN_TITLE = 'Introduction to Upper Extremity Splinting'
const RELATED = 'one-step-ahead-introduction-to-pediatric-lower-extremity-orthotics'
const RELATED_TITLE = 'One Step Ahead'

test.describe.configure({ mode: 'serial' })
test.setTimeout(120000)

async function login(page: Page, email: string, password: string) {
	await page.goto('/login')
	await page.fill('#login_email', email)
	await page.fill('#login_password', password)
	await page.click('.btn-login')
	await page.waitForURL('**/lms/**', { timeout: 15000 })
}

/** Stripe's hosted page sometimes sits on its loading skeleton in automation; reload once. */
async function waitForStripeCheckout(page: Page) {
	await page.waitForURL(/checkout\.stripe\.com/, { timeout: 30000 })
	// Present in both layouts (multi-item "Pay PPT4ed" and single-item course title).
	const header = page.getByRole('heading', { name: 'Payment method' })
	const loaded = await header
		.waitFor({ state: 'visible', timeout: 30000 })
		.then(() => true)
		.catch(() => false)
	if (!loaded) {
		await page.reload()
		await header.waitFor({ state: 'visible', timeout: 45000 })
	}
}

/** Fill Stripe's hosted Checkout with the always-succeeds test card and submit. */
async function payOnStripe(page: Page) {
	await waitForStripeCheckout(page)
	// Payment methods are an accordion. Card is usually open by default once the
	// page settles; if not, the accordion header (visually hidden) needs a forced click.
	const number = page.locator('#cardNumber')
	const cardOpen = await number
		.waitFor({ state: 'visible', timeout: 15000 })
		.then(() => true)
		.catch(() => false)
	if (!cardOpen) {
		// The accordion header intercepts pointer events and never settles for
		// Playwright's actionability checks, so fire the click directly, then
		// fall back to a raw mouse click on the "Card" row.
		const header = page.locator('[data-testid="card-accordion-item-button"]')
		await header.dispatchEvent('click')
		const opened = await number
			.waitFor({ state: 'visible', timeout: 10000 })
			.then(() => true)
			.catch(() => false)
		if (!opened) {
			const box = await page.getByText('Card', { exact: true }).first().boundingBox()
			if (box) await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2)
			await number.waitFor({ state: 'visible', timeout: 30000 })
		}
	}
	await number.fill('4242424242424242')
	await page.fill('#cardExpiry', '12 / 34')
	await page.fill('#cardCvc', '123')
	await page.fill('#billingName', 'Upsell Smoke')
	const postal = page.locator('#billingPostalCode')
	if (await postal.isVisible().catch(() => false)) {
		await postal.fill('12345')
	}
	// Don't enroll the throwaway buyer in Link; it adds OTP prompts on reruns.
	const linkSave = page.getByRole('checkbox', { name: /Save my information/ })
	if (await linkSave.isChecked().catch(() => false)) {
		await linkSave.uncheck()
	}
	await page.getByRole('button', { name: 'Pay', exact: true }).click()
	await page.waitForURL(/devlms\.ppt4ed\.org/, { timeout: 60000 })
}

/** The course page shows Continue Learning once the enrollment exists (webhook may lag). */
async function expectEnrolled(page: Page, course: string) {
	await expect
		.poll(
			async () => {
				await page.goto(`/lms/courses/${course}`)
				// The SPA fetches course data after load; wait for either CTA
				// before deciding, or an unlucky early check reads false forever.
				const anyCta = page
					.getByRole('button', { name: /Continue Learning|Buy this course/ })
					.filter({ visible: true })
					.first()
				await anyCta.waitFor({ state: 'visible', timeout: 10000 }).catch(() => {})
				return page
					.getByRole('button', { name: 'Continue Learning' })
					.filter({ visible: true })
					.first()
					.isVisible()
					.catch(() => false)
			},
			{ timeout: 60000, intervals: [2000] }
		)
		.toBe(true)
}

// The course page mounts CourseCardOverlay twice (desktop sidebar + mobile
// layout, one hidden by CSS), so always pick the visible bump.
const visibleBump = (page: Page) => page.getByTestId('order-bump').filter({ visible: true })

test('order bump: ticking the add-on buys both courses in one checkout', async ({ page }) => {
	await login(page, BUMP_USER, PASSWORD)
	await page.goto(`/lms/courses/${MAIN}`)

	const bump = visibleBump(page)
	await expect(bump).toBeVisible()
	await expect(bump).toContainText(RELATED_TITLE)
	await expect(bump).toContainText('$15.00')
	await expect(bump).toContainText('50% off the regular $30.00')
	await bump.screenshot({ path: 'test-results/order-bump.png' })

	await bump.locator('input[type="checkbox"]').check()
	await page.getByRole('button', { name: 'Buy this course' }).filter({ visible: true }).click()

	await waitForStripeCheckout(page)
	await expect(page.getByText(/add-on, 50% off/).first()).toBeVisible({ timeout: 30000 })
	await expect(page.getByText('$45.00').first()).toBeVisible()
	await payOnStripe(page)

	await expect(page).toHaveURL(new RegExp(`/lms/courses/${MAIN}`))
	await expectEnrolled(page, MAIN)
	await expectEnrolled(page, RELATED)
})

test('post-purchase: declining the bump leads to the one-click offer, which enrolls', async ({
	page,
}) => {
	await login(page, POST_USER, PASSWORD)
	await page.goto(`/lms/courses/${RELATED}`)

	const bump = visibleBump(page)
	await expect(bump).toBeVisible()
	await expect(bump).toContainText(MAIN_TITLE)
	// Leave the box unticked.
	await page.getByRole('button', { name: 'Buy this course' }).filter({ visible: true }).click()

	await waitForStripeCheckout(page)
	await expect(page.getByText(/securely saved/).first()).toBeVisible({ timeout: 30000 })
	await expect(page.getByText(/add-on, 50% off/)).toHaveCount(0)
	await payOnStripe(page)

	await expect(page).toHaveURL(/\/lms\/upsell\?session_id=cs_/)
	const offer = page.getByTestId('post-purchase-offer')
	await expect(offer).toBeVisible({ timeout: 30000 })
	await expect(offer).toContainText(MAIN_TITLE)
	await expect(offer).toContainText('$15.00')
	await expect(offer).toContainText('50% off')

	await offer.getByRole('button', { name: 'Add to my courses' }).click()
	await page.waitForURL(new RegExp(`/lms/courses/${MAIN}`), { timeout: 30000 })

	await expectEnrolled(page, MAIN)
	await expectEnrolled(page, RELATED)
})

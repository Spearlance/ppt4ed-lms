import { test, expect, Page } from '@playwright/test'

/**
 * Event upsells (PR #202) on devlms, driven end-to-end through Stripe test mode.
 *
 * Dev setup these tests assume (see lms/lms/ceu_upsell.py):
 *   - CEU Stripe Settings: enable_order_bump=1, enable_post_purchase_upsell=1, 50% off
 *   - EVENT is a published, future, paid event ($40) whose first Related Course is
 *     RELATED ($30 -> $15 at 50% off)
 *   - Two throwaway learners with no enrollments or registrations:
 *       upsell-smoke-bump@test.com / TestUser@2026!
 *       upsell-smoke-post@test.com / TestUser@2026!
 *
 * Each test makes a real test-mode charge, so run them one at a time and reset
 * the users (delete enrollments, payments, registrations, offers) before a rerun.
 */

const PASSWORD = 'TestUser@2026!'
const BUMP_USER = 'upsell-smoke-bump@test.com'
const POST_USER = 'upsell-smoke-post@test.com'

const EVENT = process.env.UPSELL_EVENT || 'upsell-smoke-event'
const RELATED = 'one-step-ahead-introduction-to-pediatric-lower-extremity-orthotics'
const RELATED_TITLE = 'One Step Ahead'

test.describe.configure({ mode: 'serial' })
test.setTimeout(150000)

async function login(page: Page, email: string, password: string) {
	await page.goto('/login')
	await page.fill('#login_email', email)
	await page.fill('#login_password', password)
	await page.click('.btn-login')
	await page.waitForURL('**/lms/**', { timeout: 15000 })
}

async function waitForStripeCheckout(page: Page) {
	await page.waitForURL(/checkout\.stripe\.com/, { timeout: 30000 })
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

async function payOnStripe(page: Page) {
	await waitForStripeCheckout(page)
	const number = page.locator('#cardNumber')
	const cardOpen = await number
		.waitFor({ state: 'visible', timeout: 15000 })
		.then(() => true)
		.catch(() => false)
	if (!cardOpen) {
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
	const linkSave = page.getByRole('checkbox', { name: /Save my information/ })
	if (await linkSave.isChecked().catch(() => false)) {
		await linkSave.uncheck()
	}
	await page.getByRole('button', { name: 'Pay', exact: true }).click()
	await page.waitForURL(/devlms\.ppt4ed\.org/, { timeout: 60000 })
}

async function expectEnrolled(page: Page, course: string) {
	await expect
		.poll(
			async () => {
				await page.goto(`/lms/courses/${course}`)
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

/** The webhook creates the registration; the logged-in learner can read their own row. */
async function expectRegistered(page: Page, event: string) {
	await expect
		.poll(
			async () => {
				const res = await page.request.get(
					`/api/resource/LMS Event Registration?fields=["name"]&filters=[["event","=","${event}"]]`
				)
				if (!res.ok()) return -1
				const body = await res.json()
				return (body.data || []).length
			},
			{ timeout: 60000, intervals: [2000] }
		)
		.toBeGreaterThan(0)
}

const visibleBump = (page: Page) => page.getByTestId('event-order-bump').filter({ visible: true })
const registerNow = (page: Page) =>
	page.getByRole('button', { name: 'Register Now' }).filter({ visible: true }).first()

test('event order bump: ticking the add-on registers for the event and buys the course', async ({
	page,
}) => {
	await login(page, BUMP_USER, PASSWORD)
	await page.goto(`/lms/events/${EVENT}`)

	const bump = visibleBump(page)
	await expect(bump).toBeVisible({ timeout: 20000 })
	await expect(bump).toContainText(RELATED_TITLE)
	await expect(bump).toContainText('$15.00')
	await expect(bump).toContainText('50% off the regular $30.00')
	await bump.screenshot({ path: 'test-results/event-order-bump.png' })

	await bump.locator('input[type="checkbox"]').check()
	await registerNow(page).click()

	await waitForStripeCheckout(page)
	await expect(page.getByText(/add-on, 50% off/).first()).toBeVisible({ timeout: 30000 })
	await expect(page.getByText('$55.00').first()).toBeVisible()
	await payOnStripe(page)

	await expect(page).toHaveURL(new RegExp(`/lms/events/${EVENT}`))
	await expectRegistered(page, EVENT)
	await expectEnrolled(page, RELATED)
})

test('event post-purchase: declining the bump leads to the one-click offer, which enrolls', async ({
	page,
}) => {
	await login(page, POST_USER, PASSWORD)
	await page.goto(`/lms/events/${EVENT}`)

	const bump = visibleBump(page)
	await expect(bump).toBeVisible({ timeout: 20000 })
	await expect(bump).toContainText(RELATED_TITLE)
	// Leave the box unticked.
	await registerNow(page).click()

	await waitForStripeCheckout(page)
	await expect(page.getByText(/securely saved/).first()).toBeVisible({ timeout: 30000 })
	await expect(page.getByText(/add-on, 50% off/)).toHaveCount(0)
	await expect(page.getByText('$40.00').first()).toBeVisible()
	await payOnStripe(page)

	await expect(page).toHaveURL(/\/lms\/upsell\?session_id=cs_/)
	const offer = page.getByTestId('post-purchase-offer')
	await expect(offer).toBeVisible({ timeout: 30000 })
	await expect(offer).toContainText(RELATED_TITLE)
	await expect(offer).toContainText('$15.00')
	await expect(offer).toContainText('50% off')
	// Event-specific decline copy from PR #202.
	await expect(page.getByRole('button', { name: /take me to my event/ })).toBeVisible()
	await offer.screenshot({ path: 'test-results/event-post-purchase-offer.png' })

	await offer.getByRole('button', { name: 'Add to my courses' }).click()
	await page.waitForURL(new RegExp(`/lms/courses/${RELATED}`), { timeout: 30000 })

	await expectRegistered(page, EVENT)
	await expectEnrolled(page, RELATED)
})

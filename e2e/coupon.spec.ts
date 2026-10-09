import { test, expect, Page } from '@playwright/test'

/**
 * Coupons (PR #206) on devlms: course and event checkout through Stripe test
 * mode with a percentage code, and a 100% event code that skips Stripe.
 *
 * Dev setup these tests assume (Settings -> Coupons):
 *   - COUPON20: 20% off, enabled, applicable to COURSE (LMS Course) and
 *     EVENT (LMS Event)
 *   - FREEEVENT: 100% off, enabled, applicable to EVENT
 *   - COURSE is a published paid course at $30; EVENT a published, future,
 *     paid event at $40 with seats left
 *   - Two throwaway learners with no enrollments or registrations:
 *       coupon-smoke-pct@test.com  / TestUser@2026!
 *       coupon-smoke-free@test.com / TestUser@2026!
 *
 * The first two tests make a real test-mode charge, so reset the users
 * (delete enrollments, payments, registrations) before a rerun.
 */

const PASSWORD = 'TestUser@2026!'
const PCT_USER = 'coupon-smoke-pct@test.com'
const FREE_USER = 'coupon-smoke-free@test.com'

const COURSE = 'one-step-ahead-introduction-to-pediatric-lower-extremity-orthotics'
const EVENT = process.env.COUPON_EVENT || 'upsell-smoke-event'

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
	await page.fill('#billingName', 'Coupon Smoke')
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

const couponBox = (page: Page) => page.getByTestId('coupon-box').filter({ visible: true }).first()
const couponPrice = (page: Page) => page.getByTestId('coupon-price').filter({ visible: true }).first()

async function applyCoupon(page: Page, code: string) {
	const box = couponBox(page)
	await expect(box).toBeVisible({ timeout: 20000 })
	await box.getByRole('button', { name: 'Have a coupon code?' }).click()
	await box.getByRole('textbox', { name: 'Coupon code' }).fill(code.toLowerCase())
	// frappe-ui Button names itself by its text; the aria-label is not exposed.
	await box.getByRole('button', { name: 'Apply', exact: true }).click()
	await expect(box).toContainText(`Coupon ${code.toUpperCase()} applied`, { timeout: 15000 })
}

test('course: COUPON20 lowers the price, Stripe charges it, buyer is enrolled', async ({ page }) => {
	await login(page, PCT_USER, PASSWORD)
	await page.goto(`/lms/courses/${COURSE}`)

	await applyCoupon(page, 'COUPON20')
	const price = couponPrice(page)
	await expect(price).toContainText('$24.00')
	await expect(price).toContainText('$30.00')
	await price.screenshot({ path: 'test-results/coupon-course-price.png' })

	await page.getByRole('button', { name: 'Buy this course' }).filter({ visible: true }).first().click()

	await waitForStripeCheckout(page)
	await expect(page.getByText(/Coupon COUPON20 \(20% off\)/).first()).toBeVisible({ timeout: 30000 })
	await expect(page.getByText('$24.00').first()).toBeVisible()
	await payOnStripe(page)

	// With the post-purchase upsell flag on, Stripe returns to /lms/upsell
	// instead of the course page. Either is fine; the enrollment is what counts.
	await expect(page).toHaveURL(new RegExp(`/lms/(courses/${COURSE}|upsell\\?session_id=)`))
	await expectEnrolled(page, COURSE)
})

test('event: COUPON20 stacks on the event price and Stripe charges it', async ({ page }) => {
	await login(page, PCT_USER, PASSWORD)
	await page.goto(`/lms/events/${EVENT}`)

	await applyCoupon(page, 'COUPON20')
	const price = couponPrice(page)
	await expect(price).toContainText('$32.00')
	await expect(price).toContainText('$40.00')

	await page.getByRole('button', { name: 'Register Now' }).filter({ visible: true }).first().click()

	await waitForStripeCheckout(page)
	await expect(page.getByText(/Coupon COUPON20 \(20% off\)/).first()).toBeVisible({ timeout: 30000 })
	await expect(page.getByText('$32.00').first()).toBeVisible()
	await payOnStripe(page)

	await expect(page).toHaveURL(new RegExp(`/lms/(events/${EVENT}|upsell\\?session_id=)`))
	await expectRegistered(page, EVENT)
})

test('event: a 100% coupon registers without Stripe', async ({ page }) => {
	await login(page, FREE_USER, PASSWORD)
	await page.goto(`/lms/events/${EVENT}`)

	await applyCoupon(page, 'FREEEVENT')
	const price = couponPrice(page)
	await expect(price).toContainText('Free')
	await expect(price).toContainText('$40.00')
	await price.screenshot({ path: 'test-results/coupon-event-free.png' })

	await page.getByRole('button', { name: 'Register for free' }).filter({ visible: true }).first().click()

	// Never leaves the site.
	await expect(page).not.toHaveURL(/checkout\.stripe\.com/)
	await expectRegistered(page, EVENT)
	await page.goto(`/lms/events/${EVENT}`)
	await expect(page.getByText('Registered').first()).toBeVisible({ timeout: 20000 })
})

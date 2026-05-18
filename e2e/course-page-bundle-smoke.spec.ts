import { test, expect, Page } from '@playwright/test'

/**
 * Post-deploy smoke for the launch-day course-page bundle:
 *   PR #119 — Short Text question type renders as single-line input
 *   PR #120 — Chapter-level gating: locks chapters past the first
 *             until prior chapters complete
 *   PR #121 — Inline completion modal fires on sub-100 → 100 transition
 *
 * Runs against devlms.ppt4ed.org. Pure smoke: no destructive state mutation,
 * no enrollment side effects. Uses pro@test.com as the student.
 */

const STUDENT_EMAIL = 'pro@test.com'
const STUDENT_PASSWORD = 'TestUser@2026!'

const CATCH_THE_WAVE =
	'catch-the-wave-introduction-to-whole-body-vibration-in-pediatric-therapy-for-pts-ots-and-slps'

async function loginAsStudent(page: Page) {
	await page.goto('/login')
	await page.fill('#login_email', STUDENT_EMAIL)
	await page.fill('#login_password', STUDENT_PASSWORD)
	await page.click('.btn-login')
	await page.waitForURL('**/lms/**', { timeout: 15000 })
}

async function logout(page: Page) {
	await page.goto('/api/method/logout')
	await page.waitForLoadState('networkidle')
}

test.describe('Course-page bundle post-deploy smoke', () => {
	test('get_course_outline returns is_locked on each chapter (PR #120)', async ({
		page,
	}) => {
		await loginAsStudent(page)

		const response = await page.request.get(
			`/api/method/lms.lms.utils.get_course_outline?course=${CATCH_THE_WAVE}&progress=true`
		)
		expect(response.ok()).toBeTruthy()

		const body = await response.json()
		const chapters = body.message
		expect(Array.isArray(chapters)).toBeTruthy()
		expect(chapters.length).toBeGreaterThan(1)

		// Every chapter must have an is_locked field
		for (const ch of chapters) {
			expect(ch).toHaveProperty('is_locked')
			expect([0, 1, true, false]).toContain(ch.is_locked)
			expect(ch.lessons.length).toBeGreaterThan(0)
			for (const lesson of ch.lessons) {
				expect(lesson).toHaveProperty('is_locked')
			}
		}

		await logout(page)
	})

	test('get_lesson on a deep chapter returns one of the three valid shapes (PR #120)', async ({
		page,
	}) => {
		await loginAsStudent(page)

		// pro@test.com isn't necessarily enrolled in Catch the Wave on dev,
		// so chapter 5 may return no_preview (non-enrolled) rather than
		// is_chapter_locked (enrolled but locked). Either is acceptable —
		// the failure mode we're guarding against is a 500 or a missing
		// field. Three legal shapes: no_preview, is_chapter_locked, or full
		// lesson payload.
		const response = await page.request.get(
			`/api/method/lms.lms.utils.get_lesson?course=${CATCH_THE_WAVE}&chapter=5&lesson=1`
		)
		expect(response.ok()).toBeTruthy()
		const body = await response.json()
		const data = body.message

		if (data.is_chapter_locked) {
			expect(data).toHaveProperty('title')
			expect(data).toHaveProperty('course_title')
		} else if (data.no_preview) {
			expect(data).toHaveProperty('title')
			expect(data).toHaveProperty('course_title')
		} else {
			expect(data).toHaveProperty('name')
			expect(data).toHaveProperty('enable_certification') // PR #121 addition
		}

		await logout(page)
	})

	test('get_lesson surfaces enable_certification (PR #121)', async ({
		page,
	}) => {
		await loginAsStudent(page)

		// Chapter 1 lesson 1 — always reachable. Check the new field is
		// present in the response.
		const response = await page.request.get(
			`/api/method/lms.lms.utils.get_lesson?course=${CATCH_THE_WAVE}&chapter=1&lesson=1`
		)
		expect(response.ok()).toBeTruthy()
		const data = (await response.json()).message

		// Allow no_preview (non-enrolled) or full lesson; not chapter-locked
		// since chapter 1 is never locked.
		expect(data.is_chapter_locked).toBeFalsy()

		// Field exists on the full-lesson branch. If no_preview, skip the
		// assertion — that path predates the field.
		if (!data.no_preview) {
			expect(data).toHaveProperty('enable_certification')
		}

		await logout(page)
	})

	test('admin Question modal exposes Short Text in Type dropdown (PR #119)', async ({
		page,
	}) => {
		// The bundle is what we care about — verify the new option is in
		// the shipped Vue chunk. We don't need to click through the modal.
		await loginAsStudent(page)

		// Pull the main app HTML to discover the Vue chunk filenames Vite emitted.
		const indexResp = await page.request.get('/lms/courses')
		const html = await indexResp.text()

		// Find the JS chunks Vite serves
		const chunks = [...html.matchAll(/\/assets\/lms\/frontend\/assets\/[A-Za-z0-9_.-]+\.js/g)].map(
			(m) => m[0]
		)
		expect(chunks.length).toBeGreaterThan(0)

		// Most likely the Question modal is in the main bundle. Scan a few
		// chunks for 'Short Text'.
		let found = false
		for (const chunk of chunks.slice(0, 12)) {
			const resp = await page.request.get(chunk)
			if (!resp.ok()) continue
			const text = await resp.text()
			if (text.includes('Short Text')) {
				found = true
				break
			}
		}

		// Fall back to fetching index chunks more broadly if not found
		if (!found) {
			for (const chunk of chunks) {
				const resp = await page.request.get(chunk)
				if (!resp.ok()) continue
				const text = await resp.text()
				if (text.includes('Short Text')) {
					found = true
					break
				}
			}
		}

		expect(found, '"Short Text" string should appear in a shipped Vue chunk').toBeTruthy()

		await logout(page)
	})

	test('Lesson page bundle ships the completion modal + chapter-lock copy (PR #121 + #120)', async ({
		page,
	}) => {
		await loginAsStudent(page)

		// Drive the browser to a real lesson route so Vite lazy-loads the
		// Lesson.vue chunk (which carries both the completion modal and the
		// "This chapter is locked" panel).
		const lessonChunks: string[] = []
		page.on('response', (resp) => {
			const url = resp.url()
			if (url.includes('/assets/lms/frontend/assets/Lesson') && url.endsWith('.js')) {
				lessonChunks.push(url)
			}
		})

		await page.goto(`/lms/courses/${CATCH_THE_WAVE}/learn/1-1`, {
			waitUntil: 'networkidle',
			timeout: 20000,
		})

		expect(lessonChunks.length, 'Lesson chunk should load on /learn/1-1').toBeGreaterThan(0)

		let foundCompletion = false
		let foundChapterLock = false
		for (const chunk of lessonChunks) {
			const resp = await page.request.get(chunk)
			if (!resp.ok()) continue
			const text = await resp.text()
			if (text.includes('Nice work')) foundCompletion = true
			if (text.includes('This chapter is locked')) foundChapterLock = true
			if (foundCompletion && foundChapterLock) break
		}

		expect(foundCompletion, '"Nice work" completion-modal copy missing from Lesson chunk').toBeTruthy()
		expect(foundChapterLock, '"This chapter is locked" copy missing from Lesson chunk').toBeTruthy()

		await logout(page)
	})
})

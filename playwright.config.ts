import { defineConfig } from '@playwright/test'

export default defineConfig({
	testDir: './e2e',
	timeout: 30000,
	expect: { timeout: 10000 },
	use: {
		baseURL: 'https://devlms.ppt4ed.org',
		screenshot: 'only-on-failure',
		trace: 'retain-on-failure',
	},
	projects: [
		{
			name: 'chromium',
			use: { browserName: 'chromium' },
		},
	],
})

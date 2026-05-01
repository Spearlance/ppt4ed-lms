<template>
	<footer
		class="border-t border-outline-gray-1 bg-surface-menu-bar text-p-xs text-ink-gray-6"
	>
		<div
			class="mx-auto flex max-w-7xl flex-col items-center justify-between gap-2 px-4 py-3 sm:flex-row sm:gap-4"
		>
			<div class="flex items-center gap-1">
				<span>&copy; {{ currentYear }} PPT4ed</span>
			</div>
			<nav
				class="flex flex-wrap items-center justify-center gap-x-4 gap-y-1"
			>
				<router-link
					v-for="link in internalLinks"
					:key="link.label"
					:to="{ name: link.routeName }"
					class="hover:text-ink-gray-9 hover:underline"
				>
					{{ __(link.label) }}
				</router-link>
				<a
					href="https://github.com/Spearlance/ppt4ed-lms"
					target="_blank"
					rel="noopener noreferrer"
					class="hover:text-ink-gray-9 hover:underline"
				>
					{{ __('Source Code (AGPL v3)') }}
				</a>
			</nav>
		</div>
	</footer>
</template>

<script setup>
import { computed } from 'vue'

const currentYear = computed(() => new Date().getFullYear())

const internalLinks = [
	{ label: 'Privacy Policy', routeName: 'PrivacyPolicy' },
	{ label: 'Terms of Service', routeName: 'TermsOfService' },
	{ label: 'Cookie Policy', routeName: 'CookiePolicy' },
]
</script>

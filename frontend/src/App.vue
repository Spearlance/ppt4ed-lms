<template>
	<FrappeUIProvider>
		<div
			v-if="isTestMode"
			class="bg-amber-400 text-amber-900 text-center text-xs font-medium py-1 px-4"
		>
			DEV MODE — Payments are test-only. Use
			<a
				href="https://docs.stripe.com/testing#cards"
				target="_blank"
				class="underline hover:text-amber-950"
			>test cards</a>
			for checkout.
		</div>
		<Layout class="isolate text-p-base">
			<router-view />
		</Layout>
		<InstallPrompt v-if="isMobile && !settings.data?.disable_pwa" />
		<Dialogs />
	</FrappeUIProvider>
</template>
<script setup>
import { FrappeUIProvider, createResource } from 'frappe-ui'
import { Dialogs } from '@/utils/dialogs'
import { storeToRefs } from 'pinia'
import { computed, onUnmounted, ref } from 'vue'
import { useScreenSize } from './utils/composables'
import { useSettings } from '@/stores/settings'
import { sessionStore } from '@/stores/session'
import { useRouter } from 'vue-router'
import DesktopLayout from './components/DesktopLayout.vue'
import MobileLayout from './components/MobileLayout.vue'
import NoSidebarLayout from './components/NoSidebarLayout.vue'
import InstallPrompt from './components/InstallPrompt.vue'

const testMode = createResource({
	url: 'lms.lms.ceu_stripe.get_stripe_test_mode',
	auto: true,
})
const isTestMode = computed(() => testMode.data === true)

const { isMobile } = useScreenSize()
const router = useRouter()
const noSidebar = ref(false)
const { settings } = useSettings()
// `storeToRefs` keeps the reactivity on the `isLoggedIn` computed so the
// Layout `computed` below tracks login/logout. Plain destructure off the
// store proxy returns the unwrapped boolean, which a) loses reactivity
// and b) makes `.value` undefined — that bug shipped in #69 and locked
// every logged-in user into NoSidebarLayout. Don't repeat that.
const { isLoggedIn } = storeToRefs(sessionStore())

router.beforeEach((to, from, next) => {
	if (to.query.fromLesson || to.path === '/persona') {
		noSidebar.value = true
	} else {
		noSidebar.value = false
	}
	next()
})

const Layout = computed(() => {
	// Guests on the public guest-allowed routes (/signup, /membership-plans,
	// resources, legal pages) shouldn't see the dashboard sidebar — its links
	// (My Credits, Notifications, etc.) require auth and just confuse the
	// signup funnel.
	if (!isLoggedIn.value || noSidebar.value) {
		return NoSidebarLayout
	}
	if (isMobile.value) {
		return MobileLayout
	}
	return DesktopLayout
})

onUnmounted(() => {
	noSidebar.value = false
})
</script>

<template>
	<div>
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs class="h-7" :items="breadcrumbs" />
		</header>
		<article
			class="mx-auto max-w-3xl px-4 py-10 sm:px-6 sm:py-14 text-ink-gray-9"
		>
			<h1 class="text-3xl font-semibold tracking-tight text-ink-gray-9">
				{{ title }}
			</h1>
			<p class="mt-2 text-p-sm text-ink-gray-6">
				{{ __('Last updated') }}: {{ lastUpdated }}
			</p>
			<div class="mt-8 space-y-6 leading-7 text-p-base">
				<slot />
			</div>
			<div class="mt-12 border-t border-outline-gray-1 pt-6 text-p-sm text-ink-gray-6">
				{{ __('Questions about this policy?') }}
				<a
					href="mailto:support@ppt4ed.org"
					class="text-ink-gray-9 underline hover:text-ink-gray-7"
				>support@ppt4ed.org</a>.
			</div>
		</article>
	</div>
</template>

<script setup>
import { computed } from 'vue'
import { Breadcrumbs } from 'frappe-ui'

const props = defineProps({
	title: { type: String, required: true },
	lastUpdated: { type: String, required: true },
	routeName: { type: String, required: true },
})

const breadcrumbs = computed(() => [
	{ label: props.title, route: { name: props.routeName } },
])
</script>

<style scoped>
:deep(h2) {
	@apply mt-8 mb-3 text-xl font-semibold text-ink-gray-9;
}
:deep(h3) {
	@apply mt-6 mb-2 text-base font-semibold text-ink-gray-9;
}
:deep(p) {
	@apply text-ink-gray-8;
}
:deep(ul) {
	@apply list-disc pl-6 text-ink-gray-8;
}
:deep(li) {
	@apply mb-1;
}
:deep(a) {
	@apply text-ink-gray-9 underline hover:text-ink-gray-7;
}
:deep(code) {
	@apply rounded bg-surface-gray-2 px-1 py-0.5 text-p-sm;
}
</style>

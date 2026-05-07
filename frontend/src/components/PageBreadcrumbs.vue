<template>
	<nav class="flex min-w-0 items-center">
		<template v-for="(item, i) in validItems" :key="i">
			<component
				:is="linkTag(item)"
				v-bind="bindings(item)"
				@click="onItemClick(item)"
				:title="isLast(i) ? item.label : null"
				class="rounded px-0.5 py-1 text-lg font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
				:class="
					isLast(i)
						? 'min-w-0 truncate text-ink-gray-9'
						: 'shrink-0 whitespace-nowrap text-ink-gray-5 hover:text-ink-gray-7'
				"
			>{{ item.label }}</component>
			<span
				v-if="!isLast(i)"
				class="mx-0.5 text-base text-ink-gray-4 shrink-0"
				aria-hidden="true"
			>/</span>
		</template>
	</nav>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
	items: { type: Array, required: true },
})

const validItems = computed(() => (props.items || []).filter(Boolean))

const isLast = (i) => i === validItems.value.length - 1

const linkTag = (item) => {
	if (item.route) return 'router-link'
	if (item.href) return 'a'
	return 'button'
}

const bindings = (item) => {
	if (item.route) return { to: item.route }
	if (item.href) return { href: item.href }
	return { type: 'button' }
}

const onItemClick = (item) => {
	if (item.onClick) item.onClick()
}
</script>

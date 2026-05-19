<template>
	<div class="space-y-1.5">
		<label v-if="label" class="block text-xs text-ink-gray-5">
			{{ label }}
			<span v-if="required" class="text-ink-red-3">*</span>
		</label>
		<Autocomplete
			ref="autocomplete"
			:options="optionsResource.data || []"
			v-model="selected"
			size="sm"
			:placeholder="placeholder"
		>
			<template #footer="{ close }">
				<div class="flex justify-between">
					<Button variant="ghost" @click="() => clearValue(close)">
						{{ __('Clear') }}
					</Button>
					<Button v-if="allowCreate" variant="ghost" @click="openCreate(close)">
						<template #prefix><Plus class="size-4 stroke-1.5" /></template>
						{{ __('New top-level category') }}
					</Button>
				</div>
			</template>
		</Autocomplete>
		<p v-if="hint" class="text-xs text-ink-gray-5">{{ hint }}</p>
	</div>
</template>

<script setup>
import Autocomplete from '@/components/Controls/Autocomplete.vue'
import { createResource, Button, toast } from 'frappe-ui'
import { Plus } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'
import { watchDebounced } from '@vueuse/core'

const props = defineProps({
	modelValue: { type: String, default: '' },
	label: { type: String, default: '' },
	placeholder: { type: String, default: 'Search categories…' },
	hint: { type: String, default: '' },
	required: { type: Boolean, default: false },
	allowCreate: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'created'])

const autocomplete = ref(null)
const query = ref('')

const optionsResource = createResource({
	url: 'lms.lms.api.get_category_options',
	auto: true,
	params: {},
})

watchDebounced(
	() => autocomplete.value?.query,
	(val) => {
		val = val || ''
		if (query.value === val) return
		query.value = val
		optionsResource.update({ params: { search: val } })
		optionsResource.reload()
	},
	{ debounce: 250, immediate: true }
)

// Autocomplete returns {value, label}; map to plain doc name out, and a
// {value, label} object in.
const selected = computed({
	get() {
		if (!props.modelValue) return null
		const match = (optionsResource.data || []).find(
			(o) => o.value === props.modelValue
		)
		return match || { value: props.modelValue, label: props.modelValue }
	},
	set(val) {
		emit('update:modelValue', val?.value || '')
	},
})

const clearValue = (close) => {
	emit('update:modelValue', '')
	close?.()
}

const createCall = createResource({
	url: 'lms.lms.api.create_category',
	onSuccess(data) {
		toast.success(__('Category created'))
		optionsResource.reload()
		emit('update:modelValue', data.name)
		emit('created', data)
	},
	onError(err) {
		toast.error(err.messages?.[0] || __('Could not create category'))
	},
})

const openCreate = (close) => {
	const label = (window.prompt(__('Name for the new top-level category:')) || '').trim()
	close?.()
	if (!label) return
	createCall.submit({ label, parent: null })
}
</script>

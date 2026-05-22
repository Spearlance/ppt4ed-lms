<template>
	<div class="space-y-1.5">
		<label v-if="label" class="block text-xs text-ink-gray-5">
			{{ label }}
			<span v-if="required" class="text-ink-red-3">*</span>
		</label>
		<div
			v-if="selectedNames.length"
			class="flex flex-wrap gap-1.5"
		>
			<span
				v-for="name in selectedNames"
				:key="name"
				class="inline-flex items-center gap-1 rounded-md bg-surface-gray-2 px-2 py-1 text-xs text-ink-gray-7"
			>
				{{ name }}
				<button
					type="button"
					class="text-ink-gray-5 hover:text-ink-gray-9"
					:aria-label="__('Remove category')"
					@click="removeCategory(name)"
				>
					<X class="h-3 w-3 stroke-1.5" />
				</button>
			</span>
		</div>
		<Autocomplete
			ref="autocomplete"
			:options="filteredOptions"
			v-model="picker"
			size="sm"
			:placeholder="placeholder"
		>
			<template #footer="{ close }">
				<div class="flex justify-between">
					<Button variant="ghost" @click="close">
						{{ __('Close') }}
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
import { Plus, X } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import { watchDebounced } from '@vueuse/core'

const props = defineProps({
	modelValue: { type: Array, default: () => [] },
	label: { type: String, default: '' },
	placeholder: { type: String, default: 'Add a category…' },
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

// `modelValue` can be either an array of plain names ("Pediatrics") or an
// array of child-row dicts ({ category: "Pediatrics", ... }) — the form
// payload shape that lands on `courseResource.doc.categories`. Normalize
// to plain names internally; emit back in the same shape we received.
const incomingIsRowDicts = computed(() =>
	props.modelValue.length > 0 && typeof props.modelValue[0] === 'object'
)
const selectedNames = computed(() => {
	if (!Array.isArray(props.modelValue)) return []
	return props.modelValue
		.map((v) => (typeof v === 'string' ? v : v?.category))
		.filter(Boolean)
})

const filteredOptions = computed(() => {
	const taken = new Set(selectedNames.value)
	return (optionsResource.data || []).filter((o) => !taken.has(o.value))
})

const emitNames = (names) => {
	if (incomingIsRowDicts.value) {
		emit(
			'update:modelValue',
			names.map((n) => ({ category: n }))
		)
	} else {
		emit('update:modelValue', names)
	}
}

const picker = computed({
	get() {
		return null
	},
	set(val) {
		const name = val?.value
		if (!name) return
		if (selectedNames.value.includes(name)) return
		emitNames([...selectedNames.value, name])
	},
})

const removeCategory = (name) => {
	emitNames(selectedNames.value.filter((n) => n !== name))
}

const createCall = createResource({
	url: 'lms.lms.api.create_category',
	onSuccess(data) {
		toast.success(__('Category created'))
		optionsResource.reload()
		if (!selectedNames.value.includes(data.name)) {
			emitNames([...selectedNames.value, data.name])
		}
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

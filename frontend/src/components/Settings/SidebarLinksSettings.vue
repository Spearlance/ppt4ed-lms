<template>
	<div class="flex flex-col min-h-0 text-base">
		<div class="flex items-center justify-between mb-5">
			<div class="flex flex-col space-y-2">
				<div class="text-xl font-semibold text-ink-gray-9">
					{{ label }}
				</div>
				<div class="text-xs text-ink-gray-5">
					{{ __(description) }}
				</div>
			</div>
			<Button @click="() => showLinkForm()">
				<template #prefix>
					<Plus v-if="!showForm" class="h-3 w-3 stroke-1.5" />
					<X v-else class="h-3 w-3 stroke-1.5" />
				</template>
				{{ showForm ? __('Close') : __('New') }}
			</Button>
		</div>

		<div v-if="showForm" class="grid grid-cols-12 gap-2 my-4">
			<FormControl
				ref="labelInput"
				v-model="form.label"
				:placeholder="__('Label (e.g. Instagram)')"
				class="col-span-3"
			/>
			<FormControl
				v-model="form.url"
				:placeholder="__('https://...')"
				class="col-span-5"
			/>
			<FormControl
				v-model="form.icon"
				:placeholder="__('Icon (e.g. Instagram)')"
				class="col-span-2"
			/>
			<FormControl
				v-model="form.display_order"
				type="number"
				:placeholder="__('Order')"
				class="col-span-1"
			/>
			<Button @click="addLink()" variant="subtle" class="col-span-1">
				{{ __('Add') }}
			</Button>
		</div>

		<div class="overflow-y-auto">
			<div class="divide-y divide-outline-gray-modals">
				<div v-if="!links.data?.length" class="py-6 text-sm text-ink-gray-5">
					{{ __('No sidebar links yet. Click New to add one.') }}
				</div>
				<div
					v-for="link in links.data"
					:key="link.name"
					class="grid grid-cols-12 gap-2 py-3 items-center group text-sm"
				>
					<div class="col-span-3 font-medium text-ink-gray-9">
						{{ link.label }}
					</div>
					<a
						:href="link.url"
						target="_blank"
						rel="noopener"
						class="col-span-4 text-ink-gray-7 hover:underline truncate"
					>
						{{ link.url }}
					</a>
					<div class="col-span-2 text-ink-gray-5">
						{{ link.icon || '—' }}
					</div>
					<div class="col-span-1 text-ink-gray-5">
						{{ link.display_order }}
					</div>
					<div class="col-span-1">
						<FormControl
							:modelValue="!!link.enabled"
							@update:modelValue="(val) => toggleEnabled(link, val)"
							type="checkbox"
						/>
					</div>
					<div class="col-span-1 text-right">
						<Button
							variant="ghost"
							theme="red"
							class="invisible group-hover:visible"
							@click="deleteLink(link.name)"
						>
							<template #icon>
								<Trash2 class="size-4 stroke-1.5 text-ink-red-4" />
							</template>
						</Button>
					</div>
				</div>
			</div>
		</div>
	</div>
</template>
<script setup>
import {
	Button,
	FormControl,
	createListResource,
	toast,
} from 'frappe-ui'
import { Plus, Trash2, X } from 'lucide-vue-next'
import { reactive, ref } from 'vue'
import { cleanError } from '@/utils'

const showForm = ref(false)
const labelInput = ref(null)
const form = reactive({
	label: '',
	url: '',
	icon: '',
	display_order: 0,
})

defineProps({
	label: { type: String, required: true },
	description: { type: String, default: '' },
})

const links = createListResource({
	doctype: 'LMS Sidebar Link',
	fields: ['name', 'label', 'url', 'icon', 'display_order', 'enabled'],
	orderBy: 'display_order asc, label asc',
	pageLength: 200,
	auto: true,
})

const resetForm = () => {
	form.label = ''
	form.url = ''
	form.icon = ''
	form.display_order = 0
}

const showLinkForm = () => {
	showForm.value = !showForm.value
	if (showForm.value) {
		setTimeout(() => labelInput.value?.$el.querySelector('input')?.focus(), 0)
	}
}

const addLink = () => {
	if (!form.label || !form.url) {
		toast.error(__('Label and URL are required'))
		return
	}
	links.insert.submit(
		{
			label: form.label,
			url: form.url,
			icon: form.icon,
			display_order: Number(form.display_order) || 0,
			enabled: 1,
		},
		{
			onSuccess() {
				links.reload()
				resetForm()
				showForm.value = false
				toast.success(__('Sidebar link added'))
			},
			onError(err) {
				toast.error(__(cleanError(err.messages?.[0]) || 'Unable to add link'))
			},
		}
	)
}

const toggleEnabled = (link, enabled) => {
	links.setValue.submit(
		{ name: link.name, enabled: enabled ? 1 : 0 },
		{
			onSuccess() {
				links.reload()
			},
			onError(err) {
				toast.error(__(cleanError(err.messages?.[0]) || 'Unable to update link'))
			},
		}
	)
}

const deleteLink = (name) => {
	links.delete.submit(name, {
		onSuccess() {
			links.reload()
			toast.success(__('Sidebar link deleted'))
		},
		onError(err) {
			toast.error(__(cleanError(err.messages?.[0]) || 'Unable to delete link'))
		},
	})
}
</script>

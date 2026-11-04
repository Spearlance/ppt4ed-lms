<template>
	<div v-if="signers.length" class="mt-3 space-y-2" data-testid="signer-credentials">
		<div class="text-xs font-medium text-ink-gray-7">
			{{ __('Signer credentials') }}
		</div>
		<div class="text-xs text-ink-gray-5">
			{{
				__(
					'Printed after each signer\'s name when Show Signer Credentials is on. Saved to their profile, so it applies everywhere they sign.'
				)
			}}
		</div>
		<div
			v-for="row in rows"
			:key="row.name"
			class="flex flex-col gap-2 rounded border border-outline-gray-2 p-2 sm:flex-row sm:items-end"
		>
			<div class="min-w-0 flex-1">
				<div class="truncate text-sm font-medium text-ink-gray-8">
					{{ row.full_name || row.name }}
				</div>
				<FormControl
					v-model="drafts[row.name]"
					type="text"
					:label="__('Credentials')"
					:placeholder="__('e.g. PT, DPT')"
					class="mt-1"
				/>
			</div>
			<Button
				:label="__('Save')"
				:disabled="!isDirty(row.name)"
				:loading="saving === row.name"
				@click="save(row.name)"
			/>
		</div>
	</div>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { Button, FormControl, createResource, toast } from 'frappe-ui'

const props = defineProps({
	signers: {
		type: Array,
		default: () => [],
	},
})

const rows = ref([])
const drafts = reactive({})
const saved = reactive({})
const saving = ref(null)

const profiles = createResource({
	url: 'lms.lms.ceu_event_admin.get_signer_profiles',
	makeParams() {
		return { users: JSON.stringify(props.signers) }
	},
	onSuccess(data) {
		rows.value = data || []
		rows.value.forEach((row) => {
			saved[row.name] = row.credentials || ''
			if (drafts[row.name] === undefined) drafts[row.name] = row.credentials || ''
		})
	},
})

const setCredentials = createResource({
	url: 'lms.lms.ceu_event_admin.set_signer_credentials',
})

const isDirty = (name) => (drafts[name] || '').trim() !== (saved[name] || '')

const save = (name) => {
	saving.value = name
	setCredentials
		.submit({ user: name, credentials: drafts[name] || '' })
		.then((res) => {
			saved[name] = res.credentials
			drafts[name] = res.credentials
			toast.success(__('Credentials saved'))
		})
		.catch((e) => {
			toast.error(e?.messages?.[0] || __('Could not save credentials'))
		})
		.finally(() => {
			saving.value = null
		})
}

watch(
	() => props.signers.slice(),
	(next) => {
		if (!next.length) {
			rows.value = []
			return
		}
		profiles.reload()
	},
	{ immediate: true }
)
</script>

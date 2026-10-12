<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Add your professional license'),
			size: 'sm',
		}"
	>
		<template #body-content>
			<form class="space-y-4" @submit.prevent="save">
				<p class="text-sm text-ink-gray-6">
					{{ reason || __('PPT cannot award CEU credit without your license type, state and number. It only takes a moment.') }}
				</p>
				<ErrorMessage v-if="errorMessage" :message="errorMessage" />
				<LicenseFields v-model="form" />
				<Button class="w-full" variant="solid" type="submit" :loading="saving">
					{{ __('Save and continue') }}
				</Button>
			</form>
		</template>
	</Dialog>
</template>

<script setup>
// Opened by the course/event overlays when a logged-in user without a
// complete license clicks Register / Enroll. On save it reloads the shared
// $user resource (so the banner and the overlays see license_complete) and
// emits `saved`, which the caller uses to resume the original action.
import { Button, call, Dialog, ErrorMessage } from 'frappe-ui'
import { inject, reactive, ref, watch } from 'vue'
import LicenseFields from '@/components/LicenseFields.vue'

const show = defineModel('open', { default: false })
const props = defineProps({
	reason: { type: String, default: '' },
})
const emit = defineEmits(['saved'])

const user = inject('$user')
const saving = ref(false)
const errorMessage = ref('')
const form = reactive({
	license_type: '',
	license_state: '',
	professional_license_number: '',
})

watch(show, (next) => {
	if (next) {
		errorMessage.value = ''
		form.license_type = user?.data?.license_type || ''
		form.license_state = user?.data?.license_state || ''
		form.professional_license_number = user?.data?.professional_license_number || ''
	}
})

async function save() {
	errorMessage.value = ''
	if (!form.license_type || !form.license_state.trim() || !form.professional_license_number.trim()) {
		errorMessage.value = __('Please enter your license type, state and number.')
		return
	}
	saving.value = true
	try {
		await call('lms.lms.license.save_my_license', {
			license_type: form.license_type,
			license_state: form.license_state.trim(),
			professional_license_number: form.professional_license_number.trim(),
		})
		await user?.reload?.()
		show.value = false
		emit('saved')
	} catch (err) {
		errorMessage.value = err?.messages?.[0] || err?.message || __('Could not save your license. Please try again.')
	} finally {
		saving.value = false
	}
}
</script>

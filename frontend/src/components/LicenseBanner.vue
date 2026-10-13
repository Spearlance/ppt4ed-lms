<template>
	<div
		v-if="user.data && !user.data.license_complete"
		class="border-b border-amber-300 bg-amber-50 text-amber-900"
		role="region"
		:aria-label="__('Professional license required')"
		data-testid="license-banner"
	>
		<div class="mx-auto flex max-w-5xl flex-col gap-3 px-4 py-3 sm:flex-row sm:items-start">
			<TriangleAlert class="mt-0.5 size-5 shrink-0 stroke-1.5 text-amber-600" />
			<div class="min-w-0 flex-1">
				<p class="text-sm font-semibold">
					{{ __('Your professional license is missing from your profile.') }}
				</p>
				<p class="text-sm">
					{{ __('PPT cannot report CEU credit to the broker without your license type, state and number. Add it now so your certificates and credits count.') }}
				</p>
				<form
					v-if="expanded"
					class="mt-3 max-w-md space-y-3 rounded-md border border-amber-200 bg-white p-3 text-ink-gray-9"
					@submit.prevent="save"
				>
					<ErrorMessage v-if="errorMessage" :message="errorMessage" />
					<LicenseFields v-model="form" />
					<div class="flex items-center gap-2">
						<Button variant="solid" type="submit" :loading="saving">
							{{ __('Save license') }}
						</Button>
						<Button variant="ghost" type="button" @click="expanded = false">
							{{ __('Not now') }}
						</Button>
					</div>
				</form>
			</div>
			<Button
				v-if="!expanded"
				variant="solid"
				class="shrink-0"
				:aria-label="__('Add license')"
				@click="expanded = true"
			>
				{{ __('Add license') }}
			</Button>
		</div>
	</div>
</template>

<script setup>
// Shown on every in-app page until the logged-in user has all three license
// fields. It saves inline (no trip to the profile page) and reloads $user so
// it disappears as soon as the save lands. Guests never see it: user.data is
// null for them.
import { Button, ErrorMessage, call } from 'frappe-ui'
import { TriangleAlert } from 'lucide-vue-next'
import { reactive, ref } from 'vue'
import LicenseFields from '@/components/LicenseFields.vue'
import { usersStore } from '@/stores/user'

// Not inject('$user'): main.js provides it only after app.mount(), and the
// layouts (where this banner lives) render during mount, so the injection
// comes back undefined there. The store holds the same resource object.
const { userResource: user } = usersStore()
const expanded = ref(false)
const saving = ref(false)
const errorMessage = ref('')
const form = reactive({
	license_type: '',
	license_state: '',
	professional_license_number: '',
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
		await user.reload()
		expanded.value = false
	} catch (err) {
		errorMessage.value = err?.messages?.[0] || err?.message || __('Could not save your license. Please try again.')
	} finally {
		saving.value = false
	}
}
</script>

<template>
	<div class="min-h-screen flex items-center justify-center bg-surface-gray-1 px-4 py-10">
		<div class="w-full max-w-md">
			<div class="text-center mb-6">
				<img
					v-if="brand.logo"
					:src="brand.logo"
					:alt="brand.name"
					class="mx-auto h-10 mb-3"
				/>
				<h1 class="text-2xl font-bold text-ink-gray-9">
					{{ heading }}
				</h1>
				<p v-if="subheading" class="text-sm text-ink-gray-5 mt-1">
					{{ subheading }}
				</p>
			</div>

			<div class="bg-surface-white border border-outline-gray-2 rounded-xl p-6 shadow-sm">
				<div v-if="invite.loading" class="text-center py-8 text-ink-gray-5">
					{{ __('Loading invitation...') }}
				</div>

				<div v-else-if="loadError">
					<ErrorMessage class="mb-4" :message="loadError" />
					<p class="text-sm text-ink-gray-5 text-center">
						{{ __('Need a new invite? Ask your company admin to send another.') }}
					</p>
				</div>

				<template v-else-if="invite.data">
					<div class="rounded-lg bg-surface-gray-2 px-4 py-3 mb-4 text-sm text-ink-gray-7">
						<div>
							<span class="text-ink-gray-5">{{ __('Invited:') }}</span>
							<b class="ml-1 text-ink-gray-9">{{ invite.data.email }}</b>
						</div>
						<div class="mt-1">
							<span class="text-ink-gray-5">{{ __('Company:') }}</span>
							<b class="ml-1 text-ink-gray-9">{{ invite.data.company_title }}</b>
						</div>
						<div v-if="invite.data.role === 'Admin'" class="mt-1">
							<Badge theme="blue">{{ __('Admin') }}</Badge>
						</div>
					</div>

					<ErrorMessage v-if="errorMessage" class="mb-4" :message="errorMessage" />

					<form class="space-y-4" @submit.prevent="submit">
						<template v-if="!invite.data.user_exists">
							<FormControl
								v-model="form.full_name"
								:label="__('Full name')"
								placeholder="Jane Doe"
								type="text"
								autocomplete="name"
								:required="true"
							/>
							<FormControl
								v-model="form.password"
								:label="__('Choose a password')"
								type="password"
								autocomplete="new-password"
								:required="true"
								:description="__('At least 8 characters.')"
							/>
						</template>
						<Button
							class="w-full"
							variant="solid"
							type="submit"
							:loading="submitting"
						>
							{{ ctaLabel }}
						</Button>
					</form>

					<p v-if="invite.data.user_exists" class="text-xs text-ink-gray-5 text-center mt-4">
						{{ __("You'll be signed in as") }} <b>{{ invite.data.email }}</b>.
					</p>
				</template>
			</div>
		</div>
	</div>
</template>

<script setup>
import { Badge, Button, call, createResource, ErrorMessage, FormControl, usePageMeta } from 'frappe-ui'
import { computed, reactive, ref } from 'vue'
import { sessionStore } from '@/stores/session'

const props = defineProps({
	token: {
		type: String,
		required: true,
	},
})

const { brand } = sessionStore()
const submitting = ref(false)
const errorMessage = ref('')

const form = reactive({
	full_name: '',
	password: '',
})

const invite = createResource({
	url: 'lms.lms.ceu_company_dashboard.get_invite_details',
	makeParams: () => ({ token: props.token }),
	auto: true,
})

const loadError = computed(() => {
	if (!invite.error) return ''
	return extractError(invite.error) || __('This invitation could not be loaded.')
})

const heading = computed(() => {
	if (invite.loading) return __('Invitation')
	if (loadError.value) return __('Invitation unavailable')
	if (!invite.data) return __('Invitation')
	if (invite.data.role === 'Admin') return __('Manage your company on PPT4ed')
	return __('Join your team on PPT4ed')
})

const subheading = computed(() => {
	if (loadError.value || !invite.data) return ''
	if (invite.data.user_exists) return __('Sign in to accept the invitation.')
	return __("Set up your account in about 30 seconds.")
})

const ctaLabel = computed(() => {
	if (!invite.data) return __('Accept')
	if (invite.data.user_exists) return __('Accept and sign in')
	return __('Create account and join')
})

function extractError(err) {
	if (!err) return null
	if (Array.isArray(err.messages) && err.messages.length) {
		return String(err.messages[0]).replace(/<[^>]+>/g, '')
	}
	return err.message ? String(err.message).replace(/<[^>]+>/g, '') : null
}

async function submit() {
	errorMessage.value = ''
	submitting.value = true
	try {
		const params = { token: props.token }
		if (!invite.data.user_exists) {
			if (!form.full_name.trim()) {
				errorMessage.value = __('Please enter your full name.')
				submitting.value = false
				return
			}
			if (!form.password || form.password.length < 8) {
				errorMessage.value = __('Password must be at least 8 characters.')
				submitting.value = false
				return
			}
			params.full_name = form.full_name.trim()
			params.password = form.password
		}
		const result = await call('lms.lms.ceu_company_dashboard.accept_company_invite', params)
		if (result?.status === 'accepted') {
			window.location.href = result.redirect_to || '/lms'
			return
		}
		errorMessage.value = __('Something went wrong. Please try again.')
	} catch (err) {
		errorMessage.value = extractError(err) || __('Something went wrong. Please try again.')
	} finally {
		submitting.value = false
	}
}

usePageMeta(() => ({
	title: __('Accept invitation'),
	icon: brand.favicon,
}))
</script>

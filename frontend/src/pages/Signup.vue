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
					{{ __('Create your account') }}
				</h1>
				<p class="text-sm text-ink-gray-5 mt-1">
					{{ __('Free, takes about 30 seconds.') }}
				</p>
			</div>

			<div class="bg-surface-white border border-outline-gray-2 rounded-xl p-6 shadow-sm">
				<ErrorMessage v-if="errorMessage" class="mb-4" :message="errorMessage" />

				<form class="space-y-4" @submit.prevent="submit">
					<FormControl
						v-model="form.full_name"
						:label="__('Full name')"
						placeholder="Jane Doe"
						type="text"
						autocomplete="name"
						:required="true"
					/>
					<FormControl
						v-model="form.email"
						:label="__('Email')"
						placeholder="jane@example.com"
						type="email"
						autocomplete="email"
						:required="true"
					/>
					<FormControl
						v-model="form.password"
						:label="__('Password')"
						type="password"
						autocomplete="new-password"
						:required="true"
						:description="__('At least 8 characters.')"
					/>
					<Button
						class="w-full"
						variant="solid"
						type="submit"
						:loading="submitting"
					>
						{{ __('Create account') }}
					</Button>
				</form>

				<p class="text-sm text-ink-gray-5 text-center mt-4">
					{{ __('Already have an account?') }}
					<a href="/login" class="text-ink-blue-link font-semibold">
						{{ __('Log in') }}
					</a>
				</p>
			</div>
		</div>
	</div>
</template>

<script setup>
import { Button, call, ErrorMessage, FormControl, usePageMeta } from 'frappe-ui'
import { reactive, ref } from 'vue'
import { sessionStore } from '@/stores/session'

const { brand } = sessionStore()

const form = reactive({
	full_name: '',
	email: '',
	password: '',
})
const submitting = ref(false)
const errorMessage = ref('')

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
		const result = await call('lms.lms.api.signup_and_enroll', {
			email: form.email.trim(),
			password: form.password,
			full_name: form.full_name.trim(),
			intent: 'free',
		})
		if (result?.status === 'logged_in') {
			window.location.href = result.redirect_to || '/lms'
			return
		}
		if (result?.status === 'exists') {
			window.location.href = `/login?redirect-to=/lms&usr=${encodeURIComponent(form.email.trim())}`
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
	title: __('Sign up'),
	icon: brand.favicon,
}))
</script>

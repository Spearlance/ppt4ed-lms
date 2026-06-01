<template>
	<Dialog
		v-model="show"
		:options="{
			title: activeTab === 'signup' ? __('Create your account') : __('Welcome back'),
			size: 'sm',
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<div class="flex border-b border-outline-gray-2">
					<button
						class="flex-1 py-2 text-sm font-semibold border-b-2 transition-colors"
						:class="activeTab === 'signup'
							? 'border-blue-500 text-ink-blue-link'
							: 'border-transparent text-ink-gray-5 hover:text-ink-gray-7'"
						@click="switchTab('signup')"
					>
						{{ __('Create account') }}
					</button>
					<button
						class="flex-1 py-2 text-sm font-semibold border-b-2 transition-colors"
						:class="activeTab === 'login'
							? 'border-blue-500 text-ink-blue-link'
							: 'border-transparent text-ink-gray-5 hover:text-ink-gray-7'"
						@click="switchTab('login')"
					>
						{{ __('Log in') }}
					</button>
				</div>

				<ErrorMessage v-if="errorMessage" :message="errorMessage" />
				<div
					v-if="infoMessage"
					class="text-sm text-ink-blue-link bg-surface-blue-2 border border-blue-100 rounded-md px-3 py-2"
				>
					{{ infoMessage }}
				</div>

				<div
					v-if="verificationSentTo"
					class="rounded-md border border-blue-100 bg-surface-blue-2 px-3 py-3 text-sm text-ink-blue-link"
				>
					<div class="font-semibold mb-1">{{ __('Check your email') }}</div>
					<p>
						{{ __('We sent a verification link to {0}. Click it to finish creating your account — the link expires in 15 minutes.').format(verificationSentTo) }}
					</p>
				</div>

				<form v-if="activeTab === 'signup' && !verificationSentTo" class="space-y-3" @submit.prevent="submitSignup">
					<p v-if="contextLabel" class="text-sm text-ink-gray-5">
						{{ __('To register for {0}').format(contextLabel) }}
					</p>
					<FormControl
						v-model="signup.full_name"
						:label="__('Full name')"
						placeholder="Jane Doe"
						type="text"
						autocomplete="name"
						:required="true"
					/>
					<FormControl
						v-model="signup.email"
						:label="__('Email')"
						placeholder="jane@example.com"
						type="email"
						autocomplete="email"
						:required="true"
					/>
					<FormControl
						v-model="signup.password"
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
						{{ submitLabel }}
					</Button>
				</form>

				<form v-else-if="!verificationSentTo" class="space-y-3" @submit.prevent="submitLogin">
					<FormControl
						v-model="login.usr"
						:label="__('Email')"
						placeholder="jane@example.com"
						type="email"
						autocomplete="email"
						:required="true"
					/>
					<FormControl
						v-model="login.pwd"
						:label="__('Password')"
						type="password"
						autocomplete="current-password"
						:required="true"
					/>
					<Button
						class="w-full"
						variant="solid"
						type="submit"
						:loading="submitting"
					>
						{{ __('Log in') }}
					</Button>
				</form>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { Button, call, Dialog, ErrorMessage, FormControl } from 'frappe-ui'
import { computed, reactive, ref, watch } from 'vue'

const show = defineModel('open', { default: false })

const props = defineProps({
	targetType: { type: String, default: null },
	targetSlug: { type: String, default: null },
	intent: { type: String, default: 'free' },
	prefillEmail: { type: String, default: '' },
	contextLabel: { type: String, default: '' },
	redirectUrl: { type: String, default: '/lms' },
})

const activeTab = ref('signup')
const submitting = ref(false)
const errorMessage = ref('')
const infoMessage = ref('')
const verificationSentTo = ref('')

const signup = reactive({
	full_name: '',
	email: '',
	password: '',
})

const login = reactive({
	usr: '',
	pwd: '',
})

watch(show, (next) => {
	if (next) {
		activeTab.value = 'signup'
		errorMessage.value = ''
		infoMessage.value = ''
		verificationSentTo.value = ''
		signup.full_name = ''
		signup.email = props.prefillEmail || ''
		signup.password = ''
		login.usr = props.prefillEmail || ''
		login.pwd = ''
	}
})

const submitLabel = computed(() => {
	if (props.intent === 'paid' || (props.intent || '').startsWith('membership:')) {
		return __('Continue to checkout')
	}
	return __('Create account')
})

function switchTab(tab) {
	activeTab.value = tab
	errorMessage.value = ''
	infoMessage.value = ''
}

function extractError(err) {
	if (!err) return null
	if (Array.isArray(err.messages) && err.messages.length) {
		return String(err.messages[0]).replace(/<[^>]+>/g, '')
	}
	if (err.exc_type === 'ValidationError' && err.exception) {
		return String(err.exception).replace(/<[^>]+>/g, '')
	}
	return err.message ? String(err.message).replace(/<[^>]+>/g, '') : null
}

async function submitSignup() {
	errorMessage.value = ''
	infoMessage.value = ''
	submitting.value = true
	try {
		const result = await call('lms.lms.api.signup_and_enroll', {
			email: signup.email.trim(),
			password: signup.password,
			full_name: signup.full_name.trim(),
			target_type: props.targetType,
			target_slug: props.targetSlug,
			intent: props.intent,
		})
		if (result?.status === 'verification_sent') {
			// PPT-domain signup gate: User row is NOT created until the user
			// clicks the link in the email. Show a holding message; modal
			// stays open so they can close it or fall back to login.
			verificationSentTo.value = result.email || signup.email.trim()
			return
		}
		if (result?.status === 'checkout_required' && result.checkout_url) {
			window.location.href = result.checkout_url
			return
		}
		if (result?.status === 'logged_in') {
			window.location.href = result.redirect_to || props.redirectUrl
			return
		}
		if (result?.status === 'exists') {
			activeTab.value = 'login'
			login.usr = signup.email.trim()
			infoMessage.value = __('That email is already registered. Log in to continue.')
			return
		}
		errorMessage.value = __('Something went wrong. Please try again.')
	} catch (err) {
		errorMessage.value = extractError(err) || __('Something went wrong. Please try again.')
	} finally {
		submitting.value = false
	}
}

async function submitLogin() {
	errorMessage.value = ''
	infoMessage.value = ''
	submitting.value = true
	try {
		const fd = new FormData()
		fd.append('cmd', 'login')
		fd.append('usr', login.usr.trim())
		fd.append('pwd', login.pwd)
		const res = await fetch('/api/method/login', {
			method: 'POST',
			body: fd,
			credentials: 'same-origin',
		})
		if (res.ok) {
			window.location.href = props.redirectUrl
			return
		}
		let msg = __('Invalid email or password.')
		try {
			const data = await res.json()
			if (data?.message) msg = String(data.message).replace(/<[^>]+>/g, '')
		} catch (e) {}
		errorMessage.value = msg
	} catch (err) {
		errorMessage.value = __('Login failed. Please try again.')
	} finally {
		submitting.value = false
	}
}
</script>

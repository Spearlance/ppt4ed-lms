<template>
	<Dialog
		v-model="show"
		:options="{
			title: dialogTitle,
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
						:class="activeTab !== 'signup'
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

				<form
					v-else-if="activeTab === 'login' && !verificationSentTo"
					class="space-y-3"
					@submit.prevent="submitLogin"
				>
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
					<div class="flex justify-end -mt-1">
						<button
							type="button"
							class="text-xs text-ink-gray-6 hover:text-ink-blue-link underline-offset-2 hover:underline"
							@click="switchTab('forgot')"
						>
							{{ __('Forgot password?') }}
						</button>
					</div>
					<Button
						class="w-full"
						variant="solid"
						type="submit"
						:loading="submitting"
					>
						{{ __('Log in') }}
					</Button>
					<template v-if="loginWithEmailLinkEnabled">
						<div class="flex items-center gap-3 text-xs text-ink-gray-5">
							<span class="h-px flex-1 bg-outline-gray-2"></span>
							<span>{{ __('or') }}</span>
							<span class="h-px flex-1 bg-outline-gray-2"></span>
						</div>
						<Button
							class="w-full"
							variant="subtle"
							type="button"
							@click="switchTab('magic')"
						>
							{{ __('Email me a login link') }}
						</Button>
					</template>
				</form>

				<form
					v-else-if="activeTab === 'forgot' && !linkSentTo"
					class="space-y-3"
					@submit.prevent="submitForgot"
				>
					<p class="text-sm text-ink-gray-6">
						{{ __("Enter your email and we'll send you a link to reset your password.") }}
					</p>
					<FormControl
						v-model="login.usr"
						:label="__('Email')"
						placeholder="jane@example.com"
						type="email"
						autocomplete="email"
						:required="true"
					/>
					<Button
						class="w-full"
						variant="solid"
						type="submit"
						:loading="submitting"
					>
						{{ __('Send reset link') }}
					</Button>
					<BackToLogin @click="switchTab('login')" />
				</form>

				<form
					v-else-if="activeTab === 'magic' && !linkSentTo"
					class="space-y-3"
					@submit.prevent="submitMagicLink"
				>
					<p class="text-sm text-ink-gray-6">
						{{ __("Enter your email and we'll send you a one-time link that logs you in without a password.") }}
					</p>
					<FormControl
						v-model="login.usr"
						:label="__('Email')"
						placeholder="jane@example.com"
						type="email"
						autocomplete="email"
						:required="true"
					/>
					<Button
						class="w-full"
						variant="solid"
						type="submit"
						:loading="submitting"
					>
						{{ __('Send login link') }}
					</Button>
					<BackToLogin @click="switchTab('login')" />
				</form>

				<div v-else-if="linkSentTo" class="space-y-3">
					<div
						class="rounded-md border border-blue-100 bg-surface-blue-2 px-3 py-3 text-sm text-ink-blue-link"
					>
						<div class="font-semibold mb-1">{{ __('Check your email') }}</div>
						<p v-if="activeTab === 'forgot'">
							{{ __('We sent password reset instructions to {0}. Once your password is reset, come back here to log in.').format(linkSentTo) }}
						</p>
						<p v-else>
							{{ __('We sent a login link to {0}. Click it to log in, then return to this page to register.').format(linkSentTo) }}
						</p>
					</div>
					<BackToLogin @click="switchTab('login')" />
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { Button, call, Dialog, ErrorMessage, FormControl } from 'frappe-ui'
import { computed, h, reactive, ref, watch } from 'vue'

// Small inline "Back to log in" link shared by the forgot / magic-link views.
const BackToLogin = {
	emits: ['click'],
	setup(_, { emit }) {
		return () =>
			h('div', { class: 'text-center' }, [
				h(
					'button',
					{
						type: 'button',
						class:
							'text-xs text-ink-gray-6 hover:text-ink-blue-link underline-offset-2 hover:underline',
						onClick: () => emit('click'),
					},
					__('Back to log in')
				),
			])
	},
}

// Set by lms/www/_lms.py boot; mirrors the gate on the standard /login page.
const loginWithEmailLinkEnabled = Boolean(window.login_with_email_link)

const show = defineModel('open', { default: false })

const props = defineProps({
	targetType: { type: String, default: null },
	targetSlug: { type: String, default: null },
	intent: { type: String, default: 'free' },
	prefillEmail: { type: String, default: '' },
	contextLabel: { type: String, default: '' },
	redirectUrl: { type: String, default: '/lms' },
})

// 'signup' | 'login' | 'forgot' | 'magic'
const activeTab = ref('signup')
const submitting = ref(false)
const errorMessage = ref('')
const infoMessage = ref('')
const verificationSentTo = ref('')
// Email a reset / login link was sent to (forgot + magic views).
const linkSentTo = ref('')

const dialogTitle = computed(() => {
	if (activeTab.value === 'signup') return __('Create your account')
	if (activeTab.value === 'forgot') return __('Reset your password')
	if (activeTab.value === 'magic') return __('Log in with a link')
	return __('Welcome back')
})

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
		linkSentTo.value = ''
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
	linkSentTo.value = ''
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

// Same endpoint the standard /login page's "Forgot Password?" uses.
// Guest-callable, rate limited by Frappe (5/hour per IP).
async function submitForgot() {
	errorMessage.value = ''
	infoMessage.value = ''
	const email = login.usr.trim()
	if (!email) {
		errorMessage.value = __('Please enter your email.')
		return
	}
	submitting.value = true
	try {
		const result = await call('frappe.core.doctype.user.user.reset_password', {
			user: email,
		})
		if (result === 'not found') {
			errorMessage.value = __('No account found with that email. Try creating one instead.')
		} else if (result === 'disabled') {
			errorMessage.value = __('This account is disabled. Please contact support.')
		} else if (result === 'not allowed') {
			errorMessage.value = __('Password reset is not allowed for this account.')
		} else {
			linkSentTo.value = email
		}
	} catch (err) {
		// Frappe returns 404 for unknown users, which `call` raises.
		if (err?.status === 404 || err?.exc_type === 'DoesNotExistError') {
			errorMessage.value = __('No account found with that email. Try creating one instead.')
		} else {
			errorMessage.value = extractError(err) || __('Could not send reset email. Please try again.')
		}
	} finally {
		submitting.value = false
	}
}

// Same endpoint as the standard /login page's "Login with Email Link".
// Server-side it silently no-ops when the setting is off, so the button is
// gated on the boot flag; the link logs the user in and lands on LMS home.
async function submitMagicLink() {
	errorMessage.value = ''
	infoMessage.value = ''
	const email = login.usr.trim()
	if (!email) {
		errorMessage.value = __('Please enter your email.')
		return
	}
	submitting.value = true
	try {
		await call('frappe.www.login.send_login_link', { email })
		linkSentTo.value = email
	} catch (err) {
		errorMessage.value = extractError(err) || __('Could not send login link. Please try again.')
	} finally {
		submitting.value = false
	}
}
</script>

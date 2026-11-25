<template>
	<div class="min-h-screen flex items-center justify-center bg-surface-gray-1 px-4 py-10">
		<div class="w-full max-w-lg">
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
			</div>

			<div class="bg-surface-white border border-outline-gray-2 rounded-xl p-6 shadow-sm">
				<div v-if="info.loading && !info.data" class="text-center py-8 text-ink-gray-5">
					{{ __('Loading...') }}
				</div>

				<div v-else-if="loadError" data-testid="private-join-invalid">
					<ErrorMessage :message="loadError" />
				</div>

				<template v-else-if="info.data">
					<h2 class="text-lg font-semibold text-ink-gray-9">
						{{ info.data.title }}
					</h2>
					<p v-if="info.data.description" class="text-sm text-ink-gray-6 mt-1">
						{{ info.data.description }}
					</p>

					<div class="rounded-lg bg-surface-gray-2 px-4 py-3 my-4 text-sm text-ink-gray-7 space-y-1">
						<div>
							<span class="text-ink-gray-5">{{ __('Date:') }}</span>
							<b class="ml-1 text-ink-gray-9">{{ dateLabel }}</b>
						</div>
						<div>
							<span class="text-ink-gray-5">{{ __('Time:') }}</span>
							<b class="ml-1 text-ink-gray-9">
								{{ formatTime(info.data.start_time) }} -
								{{ formatTime(info.data.end_time) }}
							</b>
						</div>
						<div v-if="info.data.venue">
							<span class="text-ink-gray-5">{{ __('Location:') }}</span>
							<b class="ml-1 text-ink-gray-9">{{ info.data.venue }}</b>
						</div>
						<div v-if="info.data.instructors?.length">
							<span class="text-ink-gray-5">{{ __('Instructor:') }}</span>
							<b class="ml-1 text-ink-gray-9">{{ info.data.instructors.join(', ') }}</b>
						</div>
						<div v-if="info.data.credit_hours">
							<span class="text-ink-gray-5">{{ __('CE hours:') }}</span>
							<b class="ml-1 text-ink-gray-9">{{ info.data.credit_hours }}</b>
						</div>
					</div>

					<ErrorMessage v-if="errorMessage" class="mb-4" :message="errorMessage" />

					<div v-if="info.data.registered" data-testid="private-join-registered">
						<div
							class="rounded-md border border-outline-green-2 bg-surface-green-2 px-3 py-3 text-sm text-ink-green-3 mb-4"
						>
							{{ __('You are registered. Your quiz, survey and certificate will be on the event page.') }}
						</div>
						<Button class="w-full" variant="solid" @click="goToEvent">
							{{ __('Go to the event page') }}
						</Button>
					</div>

					<div
						v-else-if="info.data.closed_reason"
						class="text-sm text-ink-gray-7"
						data-testid="private-join-closed"
					>
						{{ info.data.closed_reason }}
					</div>

					<div v-else-if="info.data.logged_in">
						<Button
							class="w-full"
							variant="solid"
							:loading="registering"
							@click="register"
						>
							{{ __('Register') }}
						</Button>
						<p class="text-xs text-ink-gray-5 text-center mt-3">
							{{ __('There is no charge. Your registration has already been covered.') }}
						</p>
					</div>

					<div v-else>
						<Button class="w-full" variant="solid" @click="showRegister = true">
							{{ __('Create an account or log in to register') }}
						</Button>
						<p class="text-xs text-ink-gray-5 text-center mt-3">
							{{ __('There is no charge. Your registration has already been covered.') }}
						</p>
					</div>
				</template>
			</div>
		</div>

		<RegisterModal
			v-model:open="showRegister"
			intent=""
			:context-label="info.data?.title || ''"
			:redirect-url="returnUrl"
			:keep-redirect-url="true"
			:require-license="true"
		/>
		<LicenseDialog
			v-model:open="showLicense"
			:reason="__('This event awards CEU credit, and the broker needs your license to report it. Add it once and you are set for every event.')"
			@saved="register"
		/>
	</div>
</template>

<script setup>
// Landing page for an event's private registration link
// (/lms/events/<event>/join/<code>). The event is unpublished, so this page
// is the only way in: it shows the event, gets the visitor logged in (or
// signed up) and registers them for free. See lms/lms/event_private_link.py.
import { Button, call, createResource, dayjs, ErrorMessage, usePageMeta } from 'frappe-ui'
import { computed, ref, watch } from 'vue'
import { sessionStore } from '@/stores/session'
import { formatTime } from '@/utils'
import RegisterModal from '@/components/Modals/RegisterModal.vue'
import LicenseDialog from '@/components/Modals/LicenseDialog.vue'

const props = defineProps({
	eventName: { type: String, required: true },
	code: { type: String, required: true },
})

const { brand } = sessionStore()
const showRegister = ref(false)
const showLicense = ref(false)
const registering = ref(false)
const errorMessage = ref('')

const basePath = `/lms/events/${props.eventName}/join/${props.code}`
// After signing up or logging in the visitor comes back here and the
// registration finishes on its own, so they do not have to click twice.
const returnUrl = `${basePath}?register=1`

const info = createResource({
	url: 'lms.lms.event_private_link.get_private_registration_info',
	makeParams: () => ({ event: props.eventName, code: props.code }),
	auto: true,
})

function extractError(err) {
	if (!err) return null
	if (Array.isArray(err.messages) && err.messages.length) {
		return String(err.messages[0]).replace(/<[^>]+>/g, '')
	}
	return err.message ? String(err.message).replace(/<[^>]+>/g, '') : null
}

const loadError = computed(() => {
	if (!info.error) return ''
	return extractError(info.error) || __('This registration link could not be loaded.')
})

const heading = computed(() => {
	if (loadError.value) return __('Registration link unavailable')
	return __('Event registration')
})

const dateLabel = computed(() =>
	info.data?.start_date ? dayjs(info.data.start_date).format('dddd, MMMM D, YYYY') : ''
)

function goToEvent() {
	window.location.href = `/lms/events/${props.eventName}`
}

async function register() {
	errorMessage.value = ''
	registering.value = true
	try {
		await call('lms.lms.event_private_link.register_with_private_link', {
			event: props.eventName,
			code: props.code,
		})
		goToEvent()
	} catch (err) {
		if (err?.exc_type === 'LicenseRequiredError') {
			showLicense.value = true
		} else {
			errorMessage.value = extractError(err) || __('Something went wrong. Please try again.')
		}
	} finally {
		registering.value = false
	}
}

let autoRegisterTried = false
watch(
	() => info.data,
	(data) => {
		if (!data || autoRegisterTried) return
		autoRegisterTried = true
		const wantsRegister = new URLSearchParams(window.location.search).get('register') === '1'
		if (wantsRegister && data.logged_in && !data.registered && !data.closed_reason) {
			register()
		}
	},
	{ immediate: true }
)

usePageMeta(() => ({
	title: info.data?.title || __('Event registration'),
}))
</script>

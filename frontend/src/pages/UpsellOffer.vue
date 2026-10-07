<template>
	<div>
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs
				:items="[
					{ label: __('Courses'), route: { name: 'Courses' } },
					{ label: __('Your purchase'), route: { name: 'UpsellOffer' } },
				]"
			/>
		</header>

		<div class="mx-auto max-w-2xl px-5 pb-16 pt-8">
			<div v-if="offer.loading && !offer.data" class="text-center text-ink-gray-5">
				{{ __('Confirming your payment...') }}
			</div>

			<div v-else-if="offer.error" class="space-y-3 text-center">
				<p class="text-ink-gray-7">
					{{ __(offer.error.messages?.[0] || 'We could not load your purchase.') }}
				</p>
				<Button variant="subtle" @click="router.push({ name: 'Courses' })">
					{{ __('Go to my courses') }}
				</Button>
			</div>

			<template v-else-if="offer.data">
				<div class="text-center">
					<CircleCheck class="mx-auto size-10 text-green-600" />
					<h1 class="mt-3 text-2xl font-semibold text-ink-gray-9">
						{{ __("You're in!") }}
					</h1>
					<p class="mt-1 text-ink-gray-6">
						{{ __('Payment received for {0}.').format(offer.data.original_title) }}
					</p>
					<p
						v-if="!offer.data.original_enrolled"
						class="mt-1 text-sm text-ink-gray-5"
						data-testid="finalizing-enrollment"
					>
						{{ __('Finalizing your enrollment...') }}
					</p>
				</div>

				<div
					v-if="offer.data.offer"
					class="mt-8 rounded-lg border bg-surface-white p-5 shadow-sm"
					data-testid="post-purchase-offer"
				>
					<div class="text-xs font-semibold uppercase tracking-wide text-ink-gray-5">
						{{ __('One-time offer') }}
					</div>
					<div class="mt-3 flex flex-col gap-4 sm:flex-row">
						<img
							v-if="offer.data.offer.image"
							:src="offer.data.offer.image"
							:alt="offer.data.offer.title"
							class="h-32 w-full shrink-0 rounded object-cover sm:h-24 sm:w-36"
						/>
						<div class="min-w-0">
							<h2 class="text-lg font-semibold text-ink-gray-9">
								{{
									__('Add {0} for {1}').format(
										offer.data.offer.title,
										formatUsd(offer.data.offer.offer_price_usd)
									)
								}}
							</h2>
							<div class="mt-1 text-sm text-ink-gray-6">
								<s>{{ formatUsd(offer.data.offer.list_price_usd) }}</s>
								·
								{{ __('{0}% off, today only').format(offer.data.offer.discount_pct) }}
								<template v-if="offer.data.offer.ceu_hours">
									· {{ offer.data.offer.ceu_hours }} {{ __('CEU Hours') }}
								</template>
							</div>
							<p
								v-if="offer.data.offer.short_introduction"
								class="mt-2 text-sm text-ink-gray-7"
							>
								{{ offer.data.offer.short_introduction }}
							</p>
						</div>
					</div>
					<div class="mt-5 flex flex-col gap-2 sm:flex-row">
						<Button
							variant="solid"
							size="md"
							:loading="accepting"
							:disabled="accepting"
							@click="accept"
						>
							{{ __('Add to my courses') }}
						</Button>
						<Button variant="subtle" size="md" :disabled="accepting" @click="decline">
							{{ __('No thanks, take me to my course') }}
						</Button>
					</div>
					<p class="mt-3 text-xs text-ink-gray-5">
						{{ __('Charged to the card you just used. No new payment details needed.') }}
					</p>
				</div>

				<div v-else class="mt-8 text-center">
					<Button variant="solid" size="md" @click="goToOriginal">
						{{ __('Go to my course') }}
					</Button>
				</div>
			</template>
		</div>
	</div>
</template>

<script setup>
import { onBeforeUnmount, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Breadcrumbs, Button, call, createResource, toast, usePageMeta } from 'frappe-ui'
import { CircleCheck } from 'lucide-vue-next'

usePageMeta({ title: 'Your purchase' })

const route = useRoute()
const router = useRouter()
const sessionId = route.query.session_id
const accepting = ref(false)

// The original course is enrolled by Stripe's webhook, which can land after
// this page does. Poll a little so the "Finalizing" line clears itself; the
// offer itself never waits on it.
const POLL_MS = 2000
const POLL_LIMIT = 15
let pollTimer = null
let polls = 0

const offer = createResource({
	url: 'lms.lms.ceu_upsell.get_upsell_offer',
	makeParams: () => ({ session_id: sessionId }),
	auto: !!sessionId,
	onSuccess(data) {
		if (data.status === 'enrolled') {
			goToCourse(data.course)
			return
		}
		if (data.original_enrolled) {
			stopPolling()
		} else if (!pollTimer && polls < POLL_LIMIT) {
			pollTimer = setInterval(() => {
				polls += 1
				if (polls >= POLL_LIMIT) stopPolling()
				offer.reload()
			}, POLL_MS)
		}
	},
})

if (!sessionId) {
	router.replace({ name: 'Courses' })
}

function stopPolling() {
	if (pollTimer) clearInterval(pollTimer)
	pollTimer = null
}

onBeforeUnmount(stopPolling)

const formatUsd = (value) => `$${Number(value || 0).toFixed(2)}`

function goToCourse(course) {
	stopPolling()
	router.push({
		name: 'CourseDetail',
		params: { courseName: course },
		query: { payment: 'success' },
	})
}

function goToOriginal() {
	goToCourse(offer.data.original_course)
}

async function accept() {
	accepting.value = true
	try {
		const result = await call('lms.lms.ceu_upsell.accept_upsell', {
			session_id: sessionId,
		})
		if (result.status === 'enrolled') {
			toast.success(__('Added to your courses'))
			goToCourse(result.course)
		} else if (result.status === 'checkout') {
			// Saved card needs the buyer (3DS or a decline): finish on Stripe.
			window.location.href = result.url
		} else {
			toast.info(__('You already have this course'))
			goToOriginal()
		}
	} catch (err) {
		accepting.value = false
		toast.warning(__(err.messages?.[0] || err.message || err))
		console.error(err)
	}
}

async function decline() {
	try {
		await call('lms.lms.ceu_upsell.decline_upsell', { session_id: sessionId })
	} catch (err) {
		console.error(err)
	}
	goToOriginal()
}
</script>

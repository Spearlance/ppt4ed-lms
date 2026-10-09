<template>
	<div v-if="batch.data" class="border-2 rounded-md lg:w-72">
		<video
			v-if="batch.data.video_link"
			:src="batch.data.video_link"
			controls
			class="rounded-t-md w-full"
		/>
		<div class="p-5">
			<Badge
				v-if="batch.data.seat_count && batch.data.seats_left > 0"
				variant="subtle"
				theme="green"
				size="md"
				:class="
					batch.data.amount || batch.data.courses.length
						? 'float-right'
						: 'w-fit mb-4'
				"
				:label="
					batch.data.seats_left +
					' ' +
					(batch.data.seats_left > 1 ? __('Seats Left') : __('Seat Left'))
				"
			/>
			<Badge
				v-else-if="batch.data.seat_count && batch.data.seats_left <= 0"
				variant="subtle"
				theme="red"
				size="md"
				class="float-right"
				:label="__('Sold Out')"
			/>
			<div
				v-if="batch.data.amount"
				class="mb-5"
			>
				<div
					v-if="coupon.data"
					class="flex items-baseline gap-2"
					data-testid="coupon-price"
				>
					<span class="text-lg font-semibold text-ink-gray-9">
						{{ coupon.data.is_free ? __('Free') : formatUsd(coupon.data.final_usd) }}
					</span>
					<span class="text-sm text-ink-gray-6 line-through">
						{{ formatUsd(coupon.data.original_usd) }}
					</span>
				</div>
				<div
					v-else-if="earlyBirdActive"
					class="flex items-baseline gap-2"
				>
					<span class="text-lg font-semibold text-ink-gray-9">
						{{ formatNumberIntoCurrency(batch.data.early_bird_amount, batch.data.currency) }}
					</span>
					<span class="text-sm text-ink-gray-6 line-through">
						{{ formatNumberIntoCurrency(batch.data.amount, batch.data.currency) }}
					</span>
				</div>
				<div
					v-else
					class="text-lg font-semibold text-ink-gray-9"
				>
					{{ formatNumberIntoCurrency(batch.data.amount, batch.data.currency) }}
				</div>
				<div
					v-if="earlyBirdActive"
					class="text-xs text-ink-green-3 mt-1"
				>
					{{ __('Early bird through') }} {{ batch.data.early_bird_deadline }}
				</div>
			</div>
			<div
				v-if="batch.data.courses.length"
				class="flex items-center mb-3 text-ink-gray-7"
			>
				<BookOpen class="h-4 w-4 stroke-1.5 mr-2" />
				<span> {{ batch.data.courses.length }} {{ __('Courses') }} </span>
			</div>
			<DateRange
				:startDate="batch.data.start_date"
				:endDate="batch.data.end_date"
				class="mb-3"
			/>
			<div
				v-if="multiDay"
				class="space-y-1 mb-3 text-ink-gray-7"
			>
				<div
					v-for="(day, idx) in batch.data.event_days"
					:key="idx"
					class="flex items-center text-sm"
				>
					<Clock class="h-4 w-4 stroke-1.5 mr-2" />
					<span>
						{{ day.date }}: {{ formatTime(day.start_time) }} -
						{{ formatTime(day.end_time) }}
					</span>
				</div>
			</div>
			<div v-else class="flex items-center mb-3 text-ink-gray-7">
				<Clock class="h-4 w-4 stroke-1.5 mr-2" />
				<span>
					{{ formatTime(batch.data.start_time) }} -
					{{ formatTime(batch.data.end_time) }}
				</span>
			</div>
			<div v-if="batch.data.timezone" class="flex items-center text-ink-gray-7">
				<Globe class="h-4 w-4 stroke-1.5 mr-2" />
				<span>
					{{ batch.data.timezone }}
				</span>
			</div>
			<div v-if="batch.data.event_type" class="flex items-center mb-3 text-ink-gray-7">
				<Monitor class="h-4 w-4 stroke-1.5 mr-2" />
				<span>
					{{ batch.data.event_type }}
				</span>
			</div>
			<div v-if="batch.data.credit_hours" class="flex items-center mb-3 text-ink-gray-7">
				<Award class="h-4 w-4 stroke-1.5 mr-2" />
				<span>
					{{ batch.data.credit_hours }} CEU {{ batch.data.credit_hours == 1 ? __('Credit') : __('Credits') }}
				</span>
			</div>
			<div v-if="batch.data.venue && batch.data.event_type === 'In-Person'" class="flex items-center mb-3 text-ink-gray-7">
				<MapPin class="h-4 w-4 stroke-1.5 mr-2" />
				<span>
					{{ batch.data.venue }}
				</span>
			</div>

			<div v-if="!readOnlyMode && !isStudent && !isInstructorOfThisEvent">
				<div
					v-if="
						orderBump.data &&
						!isPptEmployee &&
						batch.data.paid_event &&
						batch.data.seats_left > 0 &&
						batch.data.accept_enrollments
					"
					class="mt-4 rounded-md border border-dashed border-outline-gray-3 bg-surface-gray-1 p-3"
					data-testid="event-order-bump"
				>
					<FormControl
						type="checkbox"
						v-model="addUpsell"
						:label="
							__('Add {0} for {1}').format(
								orderBump.data.title,
								formatUsd(orderBump.data.offer_price_usd)
							)
						"
					/>
					<div class="mt-1 pl-6 text-xs text-ink-gray-5">
						{{
							__('{0}% off the regular {1}').format(
								orderBump.data.discount_pct,
								formatUsd(orderBump.data.list_price_usd)
							)
						}}
						<template v-if="orderBump.data.ceu_hours">
							· {{ orderBump.data.ceu_hours }} {{ __('CEU Hours') }}
						</template>
					</div>
				</div>
				<Button
					v-if="
						batch.data.paid_event &&
						isPptEmployee &&
						batch.data.seats_left > 0 &&
						batch.data.accept_enrollments
					"
					class="w-full mt-4"
					variant="solid"
					:loading="registering"
					@click="registerAsPptEmployee()"
				>
					<template #prefix>
						<GraduationCap class="size-4 stroke-1.5" />
					</template>
					<span>
						{{ __('Register Now') }}
					</span>
				</Button>
				<div
					v-else-if="
						batch.data.paid_event &&
						batch.data.seats_left > 0 &&
						batch.data.accept_enrollments
					"
					class="mt-4 space-y-3"
				>
					<div v-if="user.data" class="text-sm" data-testid="coupon-box">
						<button
							v-if="!couponOpen && !coupon.data"
							type="button"
							class="text-ink-gray-5 underline hover:text-ink-gray-7"
							@click="couponOpen = true"
						>
							{{ __('Have a coupon code?') }}
						</button>
						<div v-else-if="!coupon.data" class="flex items-center gap-2">
							<FormControl
								v-model="couponCode"
								:placeholder="__('Coupon code')"
								autocomplete="off"
								class="flex-1"
								:aria-label="__('Coupon code')"
								@input="couponCode = $event.target.value.toUpperCase()"
								@keydown.enter.prevent="applyCoupon"
							/>
							<Button
								variant="outline"
								:loading="coupon.loading"
								:aria-label="__('Apply coupon')"
								@click="applyCoupon"
							>
								{{ __('Apply') }}
							</Button>
						</div>
						<div
							v-else
							class="flex items-center justify-between gap-2 rounded-md bg-surface-gray-1 border border-outline-gray-2 px-3 py-2"
						>
							<span class="text-ink-gray-7">
								{{ __('Coupon {0} applied: {1}').format(coupon.data.code, coupon.data.label) }}
							</span>
							<Button
								variant="ghost"
								size="sm"
								:aria-label="__('Remove coupon')"
								@click="removeCoupon"
							>
								<template #icon>
									<X class="size-4 stroke-1.5" />
								</template>
							</Button>
						</div>
					</div>
					<Button
						class="w-full"
						variant="solid"
						:loading="purchasing"
						@click="purchaseEvent()"
					>
						<template #prefix>
							<CreditCard class="size-4 stroke-1.5" />
						</template>
						<span>
							{{ coupon.data?.is_free ? __('Register for free') : __('Register Now') }}
						</span>
					</Button>
				</div>
				<Button
					variant="solid"
					class="w-full mt-2"
					v-else-if="
						batch.data.allow_self_enrollment &&
						batch.data.seats_left &&
						batch.data.accept_enrollments
					"
					@click="enrollInBatch()"
				>
					<template #prefix>
						<GraduationCap class="size-4 stroke-1.5" />
					</template>
					{{ __('Enroll Now') }}
				</Button>
			</div>
			<Badge
				v-else-if="!readOnlyMode && isStudent"
				theme="green"
				size="lg"
				class="w-full mt-4"
			>
				<template #prefix>
					<CircleCheck class="size-4 stroke-1.5" />
				</template>
				{{ __('Registered') }}
			</Badge>
			<a
				v-if="batch.data.zoom_link && canAccessEvent && batch.data.webinar_window_open"
				:href="batch.data.zoom_link"
				target="_blank"
				rel="noopener noreferrer"
				class="block mt-2"
			>
				<Button variant="solid" class="w-full">
					<template #prefix>
						<Video class="size-4 stroke-1.5" />
					</template>
					{{ __('Join Webinar') }}
				</Button>
			</a>
			<div
				v-else-if="batch.data.zoom_link && canAccessEvent"
				class="mt-2 text-xs text-ink-gray-6 text-center"
			>
				{{ __('Join link unlocks 15 min before start.') }}
			</div>
		</div>
		<RegisterModal
			v-model:open="showRegister"
			target-type="event"
			:target-slug="batch.data.name"
			:intent="registerIntent"
			:context-label="batch.data.title"
			:redirect-url="`/lms/events/${batch.data.name}`"
		/>
	</div>
</template>
<script setup>
import { inject, computed, onMounted, ref } from 'vue'
import { Badge, Button, FormControl, call, createResource, toast } from 'frappe-ui'
import { useTelemetry } from 'frappe-ui/frappe'
import {
	Award,
	BookOpen,
	CircleCheck,
	Clock,
	CreditCard,
	Globe,
	GraduationCap,
	LogIn,
	MapPin,
	Monitor,
	Pencil,
	Settings,
	Video,
	X,
} from 'lucide-vue-next'
import { formatNumberIntoCurrency, formatTime } from '@/utils'
import DateRange from '@/components/Common/DateRange.vue'
import RegisterModal from '@/components/Modals/RegisterModal.vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const user = inject('$user')
const readOnlyMode = window.read_only_mode
const { capture } = useTelemetry()
const purchasing = ref(false)
const registering = ref(false)
const showRegister = ref(false)
const registerIntent = ref('free')

function openRegisterFor(intent) {
	registerIntent.value = intent
	showRegister.value = true
}

const props = defineProps({
	batch: {
		type: Object,
		default: null,
	},
})

const enroll = createResource({
	url: 'lms.lms.utils.enroll_in_event',
	makeParams(values) {
		return {
			event: props.batch.data.name,
		}
	},
})

// Order bump: the server picks the add-on course (the event's first eligible
// Related Course) and its price. The checkbox only sends "yes, add it".
const addUpsell = ref(false)
const orderBump = createResource({
	url: 'lms.lms.ceu_upsell.get_event_order_bump',
	makeParams: () => ({ event_name: props.batch.data.name }),
})

onMounted(() => {
	if (
		user.data &&
		props.batch?.data?.paid_event &&
		!user.data.is_moderator &&
		user.data.membership_type !== 'ppt_employee'
	) {
		orderBump.fetch()
	}
})

const formatUsd = (value) => `$${Number(value || 0).toFixed(2)}`

// Coupon: the server validates the code and returns the discounted price for
// display. Checkout re-validates it; nothing priced here is trusted.
const couponOpen = ref(false)
const couponCode = ref('')
const coupon = createResource({
	url: 'lms.lms.ceu_coupon.preview_coupon',
	makeParams: () => ({
		doctype: 'LMS Event',
		docname: props.batch.data.name,
		code: couponCode.value,
	}),
	onSuccess(data) {
		capture('coupon_applied', {
			event: props.batch.data.name,
			code: data.code,
		})
	},
	onError(err) {
		toast.warning(__(err.messages?.[0] || err.message || err))
	},
})

function applyCoupon() {
	if (!couponCode.value.trim()) {
		toast.warning(__('Please enter a coupon code'))
		return
	}
	coupon.fetch()
}

function removeCoupon() {
	coupon.reset()
	couponCode.value = ''
	couponOpen.value = false
}

async function purchaseEvent() {
	if (!user.data) {
		openRegisterFor('paid')
		return
	}
	purchasing.value = true
	try {
		const result = await call(
			'lms.lms.ceu_stripe.create_event_checkout',
			{
				event_name: props.batch.data.name,
				add_upsell: addUpsell.value ? 1 : 0,
				coupon_code: coupon.data?.code || null,
			}
		)
		if (result.status === 'enrolled') {
			// 100% coupon: registered server-side, no Stripe step.
			capture('registered_for_event', {
				event: props.batch.data.name,
				source: 'coupon',
			})
			toast.success(__('You have been registered for this event'))
			router.push({
				name: 'Event',
				params: { eventName: props.batch.data.name },
			})
			return
		}
		capture('stripe_event_checkout_started', {
			event: props.batch.data.name,
			order_bump: addUpsell.value,
			coupon: coupon.data?.code || null,
		})
		window.location.href = result.url
	} catch (err) {
		purchasing.value = false
		toast.warning(__(err.messages?.[0] || err.message || err))
		console.error(err)
	}
}

async function registerAsPptEmployee() {
	if (!user.data) {
		openRegisterFor('free')
		return
	}
	registering.value = true
	try {
		await call('lms.lms.ceu_enrollment.register_ppt_employee_for_event', {
			event_name: props.batch.data.name,
			membership_name: user.data.membership_name,
		})
		capture('registered_for_event', {
			event: props.batch.data.name,
			source: 'ppt_employee',
		})
		toast.success(__('You have been registered for this event'))
		router.push({
			name: 'Event',
			params: { eventName: props.batch.data.name },
		})
	} catch (err) {
		registering.value = false
		toast.warning(__(err.messages?.[0] || err.message || err))
		console.error(err)
	}
}

const enrollInBatch = () => {
	if (!user.data) {
		openRegisterFor('free')
		return
	}
	enroll.submit(
		{},
		{
			onSuccess(data) {
				toast.success(__('You have been enrolled in this event'))
				router.push({
					name: 'Event',
					params: {
						eventName: props.batch.data.name,
					},
				})
			},
			onError(err) {
				toast.error(__(err.messages?.[0] || err))
				console.error(err)
			},
		}
	)
}

const isStudent = computed(() => {
	return user.data
		? props.batch.data?.students?.includes(user.data?.name)
		: false
})

const isModerator = computed(() => {
	return user.data?.is_moderator
})

const isPptEmployee = computed(
	() => user.data?.membership_type === 'ppt_employee'
)

const isAdmin = computed(() => {
	return user.data?.is_moderator
})

const isInstructorOfThisEvent = computed(() => {
	const instructors = props.batch?.data?.instructors || []
	return instructors.some((i) => i.name === user.data?.name)
})

const canAccessEvent = computed(() => {
	if (!user.data) {
		return false
	}
	return isModerator.value || isStudent.value
})

const multiDay = computed(() => {
	const days = props.batch?.data?.event_days || []
	return days.length > 1
})

const earlyBirdActive = computed(() => {
	const data = props.batch?.data
	if (!data?.paid_event) return false
	if (!data.early_bird_deadline) return false
	const eb = data.early_bird_amount || data.early_bird_amount_usd
	if (!eb || Number(eb) <= 0) return false
	const today = new Date()
	today.setHours(0, 0, 0, 0)
	const deadline = new Date(data.early_bird_deadline)
	return today <= deadline
})
</script>

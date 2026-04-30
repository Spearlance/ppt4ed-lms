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
					v-if="earlyBirdActive"
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

			<div v-if="!readOnlyMode && !canAccessEvent">
				<Button
					v-if="
						batch.data.paid_event &&
						batch.data.seats_left > 0 &&
						batch.data.accept_enrollments
					"
					class="w-full mt-4"
					variant="solid"
					:loading="purchasing"
					@click="purchaseEvent()"
				>
					<template #prefix>
						<CreditCard class="size-4 stroke-1.5" />
					</template>
					<span>
						{{ __('Register Now') }}
					</span>
				</Button>
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
		</div>
	</div>
</template>
<script setup>
import { inject, computed, ref } from 'vue'
import { Badge, Button, call, createResource, toast } from 'frappe-ui'
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
} from 'lucide-vue-next'
import { formatNumberIntoCurrency, formatTime } from '@/utils'
import DateRange from '@/components/Common/DateRange.vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const user = inject('$user')
const readOnlyMode = window.read_only_mode
const { capture } = useTelemetry()
const purchasing = ref(false)

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

async function purchaseEvent() {
	if (!user.data) {
		toast.warning(__('You need to login first to register for this event'))
		setTimeout(() => {
			window.location.href = `/login?redirect-to=${window.location.pathname}`
		}, 500)
		return
	}
	purchasing.value = true
	try {
		const result = await call(
			'lms.lms.ceu_stripe.create_event_checkout',
			{ event_name: props.batch.data.name }
		)
		capture('stripe_event_checkout_started', { event: props.batch.data.name })
		window.location.href = result.url
	} catch (err) {
		purchasing.value = false
		toast.warning(__(err.messages?.[0] || err.message || err))
		console.error(err)
	}
}

const enrollInBatch = () => {
	if (!user.data) {
		window.location.href = `/login?redirect-to=/events/${props.batch.data.name}`
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

const isAdmin = computed(() => {
	return user.data?.is_moderator
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

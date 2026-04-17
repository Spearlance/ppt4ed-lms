<template>
	<div class="border-2 rounded-md min-w-80 max-w-sm">
		<iframe
			v-if="course.data.video_link"
			:src="video_link"
			class="rounded-t-md min-h-56 w-full"
		/>
		<div class="p-5">
			<div v-if="course.data.paid_course" class="text-2xl font-semibold mb-3">
				{{ course.data.price }}
			</div>
			<div v-if="!readOnlyMode">
				<div v-if="course.data.membership" class="space-y-2 mb-8">
					<router-link
						:to="{
							name: 'Lesson',
							params: {
								courseName: course.name,
								chapterNumber: course.data.current_lesson
									? course.data.current_lesson.split('-')[0]
									: 1,
								lessonNumber: course.data.current_lesson
									? course.data.current_lesson.split('-')[1]
									: 1,
							},
						}"
					>
						<Button variant="solid" size="md" class="w-full">
							<template #prefix>
								<BookText class="size-4 stroke-1.5" />
							</template>
							<span>
								{{ __('Continue Learning') }}
							</span>
						</Button>
					</router-link>
					<CertificationLinks :courseName="course.data.name" class="w-full" />
				</div>
				<div
					v-else-if="isCompanyMember && courseCeuHours > 0 && !isAdmin"
					class="space-y-2 mb-8"
				>
					<Button
						@click="showConfirmDialog = true"
						variant="solid"
						size="md"
						class="w-full"
						:disabled="insufficientCredits"
					>
						<template #prefix>
							<BookText class="size-4 stroke-1.5" />
						</template>
						<span>
							{{ __('Enroll') }} — {{ courseCeuHours }} CEU
							{{ courseCeuHours === 1 ? __('hour') : __('hours') }}
						</span>
					</Button>
					<div class="text-xs text-ink-gray-5 text-center">
						{{ __('From your {0} account').format(user.data.company_name) }}
						<span
							v-if="insufficientCredits"
							class="text-red-600 block mt-1"
						>
							{{ __('Insufficient credits ({0} available)').format(user.data.company_credit_balance) }}
						</span>
					</div>
				</div>
				<div
					v-else-if="isPptEmployee && !isAdmin"
					class="space-y-2 mb-8"
				>
					<div v-if="pptVerificationSent" class="text-center p-4 bg-blue-50 rounded-md">
						<div class="font-medium text-ink-gray-9 mb-1">
							{{ __('Check your inbox') }}
						</div>
						<div class="text-sm text-ink-gray-7">
							{{ __('We sent a confirmation link to your email. Click it to start the course.') }}
						</div>
					</div>
					<template v-else>
						<Button
							@click="enrollPptEmployee()"
							variant="solid"
							size="md"
							class="w-full"
						>
							<template #prefix>
								<BookText class="size-4 stroke-1.5" />
							</template>
							<span>
								{{ __('Start Learning') }}
							</span>
						</Button>
						<div class="text-xs text-ink-gray-5 text-center">
							{{ __('Included with your PPT employee account') }}
						</div>
					</template>
				</div>
				<Button
					v-else-if="course.data.paid_course && !isAdmin"
					@click="purchaseCourse()"
					variant="solid"
					size="md"
					class="w-full mb-8"
					:loading="purchasing"
				>
					<template #prefix>
						<CreditCard class="size-4 stroke-1.5" />
					</template>
					<span>
						{{ __('Buy this course') }}
					</span>
				</Button>
				<Badge
					v-else-if="course.data.disable_self_learning && !isAdmin"
					theme="blue"
					size="lg"
					class="mb-4"
				>
					{{ __('Contact the Administrator to enroll for this course') }}
				</Badge>
				<Button
					v-else-if="!isAdmin"
					@click="enrollStudent()"
					variant="solid"
					class="w-full mb-8"
					size="md"
				>
					<template #prefix>
						<BookText class="size-4 stroke-1.5" />
					</template>
					<span>
						{{ __('Start Learning') }}
					</span>
				</Button>
				<Button
					v-if="canGetCertificate"
					@click="fetchCertificate()"
					variant="subtle"
					class="w-full mt-2"
					size="md"
				>
					<template #prefix>
						<GraduationCap class="size-4 stroke-1.5" />
					</template>
					{{ __('Get Certificate') }}
				</Button>
			</div>
			<div class="space-y-3">
				<div class="font-medium text-ink-gray-9">
					{{ __('This course has:') }}
				</div>
				<div class="flex items-center text-ink-gray-9">
					<BookOpen class="h-4 w-4 stroke-1.5" />
					<span class="ml-2">
						{{ course.data.lessons }}
						{{ course.data.lessons > 1 ? __('lessons') : __('lesson') }}
					</span>
				</div>
				<div class="flex items-center text-ink-gray-9">
					<Users class="h-4 w-4 stroke-1.5" />
					<span class="ml-2">
						{{ formatAmount(course.data.enrollments) }}
						{{
							course.data.enrollments > 1
								? __('enrolled students')
								: __('enrolled student')
						}}
					</span>
				</div>
				<div
					v-if="parseInt(course.data.rating) > 0"
					class="flex items-center text-ink-gray-9"
				>
					<Star class="size-4 stroke-1.5 fill-yellow-500 text-transparent" />
					<span class="ml-2">
						{{ course.data.rating }} {{ __('average rating') }}
					</span>
				</div>
				<div
					v-if="course.data.enable_certification"
					class="flex items-center font-semibold text-ink-gray-9"
				>
					<GraduationCap class="h-4 w-4 stroke-2" />
					<span class="ml-2">
						{{ __('Certificate of Completion') }}
					</span>
				</div>
				<div
					v-if="course.data.paid_certificate"
					class="flex items-center font-semibold text-ink-gray-9"
				>
					<GraduationCap class="h-4 w-4 stroke-2" />
					<span class="ml-2">
						{{ __('Paid Certificate after Evaluation') }}
					</span>
				</div>
			</div>
		</div>
	</div>
	<Dialog
		v-model="showConfirmDialog"
		:options="{
			title: __('Confirm Enrollment'),
			size: 'sm',
		}"
	>
		<template #body-content>
			<div class="space-y-3 text-ink-gray-7">
				<div class="flex justify-between">
					<span>{{ __('Current Balance') }}</span>
					<span class="font-semibold text-ink-gray-9">
						{{ user.data.company_credit_balance }} {{ __('hours') }}
					</span>
				</div>
				<div class="flex justify-between">
					<span>{{ __('Course Cost') }}</span>
					<span class="font-semibold text-ink-gray-9">
						{{ courseCeuHours }} {{ courseCeuHours === 1 ? __('hour') : __('hours') }}
					</span>
				</div>
				<hr class="border-outline-gray-2" />
				<div class="flex justify-between">
					<span>{{ __('Remaining Balance') }}</span>
					<span class="font-semibold text-ink-gray-9">
						{{ user.data.company_credit_balance - courseCeuHours }} {{ __('hours') }}
					</span>
				</div>
			</div>
		</template>
		<template #actions="{ close }">
			<div class="flex justify-end space-x-2 pb-5">
				<Button variant="subtle" @click="close()">
					{{ __('Cancel') }}
				</Button>
				<Button variant="solid" @click="confirmEnroll(close)">
					{{ __('Confirm Enrollment') }}
				</Button>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import {
	BookOpen,
	BookText,
	CreditCard,
	GraduationCap,
	Pencil,
	Star,
	TrendingUp,
	Users,
} from 'lucide-vue-next'
import { computed, inject, ref } from 'vue'
import { Badge, Button, call, createResource, Dialog, toast } from 'frappe-ui'
import { formatAmount } from '@/utils/'
import { useRouter } from 'vue-router'
import CertificationLinks from '@/components/CertificationLinks.vue'
import { useTelemetry } from 'frappe-ui/frappe'

const router = useRouter()
const user = inject('$user')
const readOnlyMode = window.read_only_mode
const { capture } = useTelemetry()

const props = defineProps({
	course: {
		type: Object,
		default: null,
	},
})

const video_link = computed(() => {
	if (props.course.data.video_link) {
		return 'https://www.youtube.com/embed/' + props.course.data.video_link
	}
	return null
})

function enrollStudent() {
	if (!user.data) {
		toast.warning(__('You need to login first to enroll for this course'))
		setTimeout(() => {
			window.location.href = `/login?redirect-to=${window.location.pathname}`
		}, 500)
	} else {
		call('frappe.client.insert', {
			doc: {
				doctype: 'LMS Enrollment',
				course: props.course.data.name,
				member: user.data.name,
			},
		})
			.then(() => {
				capture('enrolled_in_course', {
					course: props.course.data.name,
				})
				toast.success(__('You have been enrolled in this course'))
				setTimeout(() => {
					router.push({
						name: 'Lesson',
						params: {
							courseName: props.course.data.name,
							chapterNumber: 1,
							lessonNumber: 1,
						},
					})
				}, 1000)
			})
			.catch((err) => {
				toast.warning(__(err.messages?.[0] || err))
				console.error(err)
			})
	}
}

const is_instructor = () => {
	let user_is_instructor = false
	props.course.data.instructors.forEach((instructor) => {
		if (!user_is_instructor && instructor.name == user.data?.name) {
			user_is_instructor = true
		}
	})
	return user_is_instructor
}

const canGetCertificate = computed(() => {
	if (
		props.course.data?.enable_certification &&
		props.course.data?.membership?.progress == 100
	) {
		return true
	}
	return false
})

const certificate = createResource({
	url: 'lms.lms.doctype.lms_certificate.lms_certificate.create_certificate',
	makeParams(values) {
		return {
			course: values.course,
		}
	},
	onSuccess(data) {
		window.open(
			`/api/method/frappe.utils.print_format.download_pdf?doctype=LMS+Certificate&name=${
				data.name
			}&format=${encodeURIComponent(data.template)}`,
			'_blank'
		)
	},
})

const fetchCertificate = () => {
	certificate.submit({
		course: props.course.data?.name,
		member: user.data?.name,
	})
}

const isAdmin = computed(() => {
	return user.data?.is_moderator || is_instructor()
})

const isCompanyMember = computed(() => user.data?.is_company_member)

const isPptEmployee = computed(() => user.data?.membership_type === 'ppt_employee')

const courseCeuHours = computed(() => props.course.data?.ceu_hours || 0)

const insufficientCredits = computed(() => {
	return (user.data?.company_credit_balance || 0) < courseCeuHours.value
})

async function confirmEnroll(close) {
	close()
	await enrollViaCompany()
}

async function enrollViaCompany() {
	if (!user.data) {
		toast.warning(__('You need to login first to enroll for this course'))
		setTimeout(() => {
			window.location.href = `/login?redirect-to=${window.location.pathname}`
		}, 500)
		return
	}
	try {
		const result = await call(
			'lms.lms.ceu_enrollment.enroll_company_member',
			{
				course_name: props.course.data.name,
				company_name: user.data.company_account,
			}
		)
		if (result.status === 'enrolled') {
			capture('enrolled_in_course', {
				course: props.course.data.name,
				source: 'company_credits',
			})
			toast.success(__('You have been enrolled in this course'))
			setTimeout(() => {
				router.push({
					name: 'Lesson',
					params: {
						courseName: props.course.data.name,
						chapterNumber: 1,
						lessonNumber: 1,
					},
				})
			}, 1000)
		}
	} catch (err) {
		toast.warning(__(err.messages?.[0] || err))
		console.error(err)
	}
}

const pptVerificationSent = ref(false)
const showConfirmDialog = ref(false)
const purchasing = ref(false)

async function purchaseCourse() {
	if (!user.data) {
		toast.warning(__('You need to login first to purchase this course'))
		setTimeout(() => {
			window.location.href = `/login?redirect-to=${window.location.pathname}`
		}, 500)
		return
	}
	purchasing.value = true
	try {
		const result = await call(
			'lms.lms.ceu_stripe.create_one_off_checkout',
			{ course_name: props.course.data.name }
		)
		capture('stripe_checkout_started', { course: props.course.data.name })
		window.location.href = result.url
	} catch (err) {
		purchasing.value = false
		toast.warning(__(err.messages?.[0] || err.message || err))
		console.error(err)
	}
}

async function enrollPptEmployee() {
	if (!user.data) {
		toast.warning(__('You need to login first to enroll for this course'))
		setTimeout(() => {
			window.location.href = `/login?redirect-to=${window.location.pathname}`
		}, 500)
		return
	}
	try {
		const result = await call(
			'lms.lms.ceu_enrollment.enroll_ppt_employee',
			{
				course_name: props.course.data.name,
				membership_name: user.data.membership_name,
			}
		)
		if (result.status === 'verification_sent') {
			pptVerificationSent.value = true
		}
	} catch (err) {
		toast.warning(__(err.messages?.[0] || err))
		console.error(err)
	}
}
</script>

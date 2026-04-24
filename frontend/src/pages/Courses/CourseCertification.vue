<template>
	<header
		class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs class="h-7" :items="breadcrumbs" />
	</header>
	<div class="p-5">
		<div v-if="certificate.data && Object.keys(certificate.data).length">
			<div class="text-lg text-ink-gray-9 font-semibold mb-1">
				{{ __('Certification') }}
			</div>
			<div class="text-ink-gray-9 text-sm">
				{{
					__(
						'You are already certified for this course. Click on the card below to open your certificate.'
					)
				}}
			</div>
			<div
				class="border p-3 w-fit min-w-60 rounded-md space-y-2 hover:bg-surface-gray-1 cursor-pointer mt-5"
				@click="openCertificate(certificate.data)"
			>
				<div class="text-ink-gray-9 font-semibold">
					{{ courseTitle }}
				</div>
				<div class="text-sm text-ink-gray-7 font-medium">
					{{ __('Issued On') }}:
					{{ dayjs(certificate.data.issue_date).format('DD MMM YYYY') }}
				</div>
				<div
					v-if="certificate.data.ceu_hours"
					class="text-sm text-ink-gray-7"
				>
					{{ certificate.data.ceu_hours }} {{ __('CEU Hours') }}
					<span v-if="certificate.data.ceu_disciplines" class="text-ink-gray-5">
						· {{ certificate.data.ceu_disciplines }}
					</span>
				</div>
			</div>
		</div>
		<div v-else class="text-ink-gray-7 space-y-3">
			<div>
				{{
					__(
						'Complete the course — including the final feedback survey — to earn your certificate.'
					)
				}}
			</div>
			<Button
				variant="solid"
				@click="
					router.push({
						name: 'CourseDetail',
						params: { courseName: props.courseName },
					})
				"
			>
				{{ __('Return to Course') }}
			</Button>
		</div>
	</div>
</template>
<script setup>
import { computed, inject, onMounted, ref } from 'vue'
import {
	Breadcrumbs,
	Button,
	call,
	createResource,
	usePageMeta,
} from 'frappe-ui'
import { useRouter } from 'vue-router'
import { sessionStore } from '../../stores/session'
const courseTitle = ref(null)
const { brand } = sessionStore()
const user = inject('$user')
const dayjs = inject('$dayjs')
const router = useRouter()

const props = defineProps({
	courseName: {
		type: String,
		required: true,
	},
})

onMounted(() => {
	fetchEnrollmentDetails()
	fetchCourseDetails()
})

const certificate = createResource({
	url: 'frappe.client.get_value',
	params: {
		doctype: 'LMS Certificate',
		filters: {
			member: user.data?.name,
			course: props.courseName,
		},
		fieldname: ['name', 'template', 'issue_date', 'ceu_hours', 'ceu_disciplines'],
	},
	cache: [user.data?.name, props.courseName],
})

const fetchEnrollmentDetails = () => {
	call('frappe.client.get_value', {
		doctype: 'LMS Enrollment',
		filters: { member: user.data?.name, course: props.courseName },
		fieldname: ['purchased_certificate'],
	}).then((data) => {
		if (data.purchased_certificate) {
			certificate.reload()
		} else {
			router.push({
				name: 'CourseDetail',
				params: { courseName: props.courseName },
			})
		}
	})
}

const fetchCourseDetails = () => {
	call('frappe.client.get_value', {
		doctype: 'LMS Course',
		filters: { name: props.courseName },
		fieldname: ['title'],
	}).then((data) => {
		courseTitle.value = data.title
	})
}

const openCertificate = (certificate) => {
	window.open(
		`/api/method/frappe.utils.print_format.download_pdf?doctype=LMS+Certificate&name=${
			certificate.name
		}&format=${encodeURIComponent(certificate.template)}`,
		'_blank'
	)
}

const breadcrumbs = computed(() => [
	{
		label: __('Courses'),
		route: { name: 'Courses' },
	},
	{
		label: courseTitle.value,
		route: { name: 'CourseDetail', params: { courseName: props.courseName } },
	},
	{
		label: __('Certification'),
	},
])

usePageMeta(() => {
	return {
		title: courseTitle.value,
		icon: brand.favicon,
	}
})
</script>

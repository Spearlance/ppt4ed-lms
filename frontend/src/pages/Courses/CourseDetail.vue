<template>
	<div v-if="course.data">
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs class="h-7 min-w-0 flex-1 mr-2" :items="breadcrumbs" />
			<div class="flex items-center space-x-2 shrink-0">
				<a
					v-if="course.data.published && publicUrl"
					:href="publicUrl"
					target="_blank"
					rel="noopener"
					class="hidden sm:inline-flex items-center gap-1.5 text-xs font-medium text-ink-gray-7 hover:text-ink-gray-9 border border-outline-gray-2 hover:border-outline-gray-3 rounded-md px-2 py-1 max-w-xs truncate"
					:title="publicUrl"
					@click.prevent="copyPublicUrl"
				>
					<Link2 class="w-3.5 h-3.5 stroke-1.5 shrink-0" />
					<span class="truncate">{{ publicUrlShort }}</span>
				</a>
				<div v-if="tabIndex == 2" class="flex items-center space-x-2">
					<Badge v-if="childRef?.isDirty" theme="orange">
						{{ __('Not Saved') }}
					</Badge>
					<Button @click="childRef.trashCourse()">
						<template #icon>
							<Trash2 class="w-4 h-4 stroke-1.5" />
						</template>
					</Button>
					<Button variant="solid" @click="childRef.submitCourse()">
						{{ __('Save') }}
					</Button>
				</div>
			</div>
		</header>
		<CourseOverview v-if="!isAdmin" :course="course" />
		<div v-else>
			<Tabs :tabs="tabs" v-model="tabIndex">
				<template #tab-panel="{ tab }">
					<component :is="tab.component" :course="course" ref="childRef" />
				</template>
			</Tabs>
		</div>
	</div>
</template>
<script setup>
import {
	Badge,
	Button,
	createResource,
	Tabs,
	toast,
	usePageMeta,
} from 'frappe-ui'
import Breadcrumbs from '@/components/PageBreadcrumbs.vue'
import { computed, inject, markRaw, onMounted, ref, watch } from 'vue'
import { sessionStore } from '@/stores/session'
import { useRouter, useRoute } from 'vue-router'
import { Link2, List, Settings2, Trash2, TrendingUp } from 'lucide-vue-next'
import CourseOverview from '@/pages/Courses/CourseOverview.vue'
import CourseDashboard from '@/pages/Courses/CourseDashboard.vue'
import CourseForm from '@/pages/Courses/CourseForm.vue'

const { brand } = sessionStore()
const router = useRouter()
const route = useRoute()
const user = inject('$user')
const tabIndex = ref(0)
const childRef = ref(null)

const props = defineProps({
	courseName: {
		type: String,
		required: true,
	},
})

onMounted(() => {
	updateTabIndex()
	handlePaymentReturn()
})

function handlePaymentReturn() {
	const status = route.query.payment
	if (!status) return
	if (status === 'success') {
		toast.success(__('Payment received — enrolling you now'))
		setTimeout(() => course.reload(), 2000)
	} else if (status === 'cancelled') {
		toast.info(__('Payment cancelled'))
	}
	router.replace({ query: { ...route.query, payment: undefined } })
}

const updateTabIndex = () => {
	const hash = route.hash
	if (hash) {
		tabs.value.forEach((tab, index) => {
			if (tab.label?.toLowerCase() === hash.replace('#', '')) {
				tabIndex.value = index
			}
		})
	}
}

watch(tabIndex, () => {
	const tab = tabs.value[tabIndex.value]
	if (tab.label != route.hash.replace('#', '')) {
		router.push({ ...route, hash: `#${tab.label.toLowerCase()}` })
	}
})

const course = createResource({
	url: 'lms.lms.utils.get_course_details',
	cache: ['course', props.courseName],
	makeParams() {
		return {
			course: props.courseName,
		}
	},
	auto: true,
})

const publicUrl = computed(() => {
	const r = course.data?.route
	return r ? `${window.location.origin}/${r}` : null
})

const publicUrlShort = computed(() => {
	const r = course.data?.route
	return r ? `/${r}` : ''
})

async function copyPublicUrl() {
	if (!publicUrl.value) return
	try {
		await navigator.clipboard.writeText(publicUrl.value)
		toast.success(__('Public link copied'))
	} catch (e) {
		window.open(publicUrl.value, '_blank', 'noopener')
	}
}

const tabs = ref([
	{
		label: __('Overview'),
		component: markRaw(CourseOverview),
		icon: List,
	},
	{
		label: __('Dashboard'),
		component: markRaw(CourseDashboard),
		icon: TrendingUp,
	},
	{
		label: __('Settings'),
		component: markRaw(CourseForm),
		icon: Settings2,
	},
])

watch(
	() => props.courseName,
	() => {
		course.reload()
	}
)

watch(course, () => {
	if (!isAdmin.value && !course.data?.published && !course.data?.upcoming) {
		router.push({
			name: 'Courses',
		})
	}
})

const isInstructor = () => {
	let user_is_instructor = false
	course.data?.instructors.forEach((instructor) => {
		if (!user_is_instructor && instructor.name == user.data?.name) {
			user_is_instructor = true
		}
	})
	return user_is_instructor
}

const isAdmin = computed(() => {
	return user.data?.is_moderator || isInstructor()
})

const breadcrumbs = computed(() => {
	let crumbs = [{ label: __('Courses'), route: { name: 'Courses' } }]
	crumbs.push({
		label: course?.data?.title,
		route: { name: 'CourseDetail', params: { courseName: course?.data?.name } },
	})
	return crumbs
})

usePageMeta(() => {
	return {
		title: course?.data?.title,
		icon: brand.favicon,
	}
})
</script>
<style>
.avatar-group {
	display: inline-flex;
	align-items: center;
}

.avatar-group .avatar {
	transition: margin 0.1s ease-in-out;
}
</style>

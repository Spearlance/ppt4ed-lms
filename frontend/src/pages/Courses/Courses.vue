<template>
	<header
		class="sticky flex items-center justify-between top-0 z-10 border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />

		<Dropdown
			placement="right"
			side="bottom"
			v-if="canCreateCourse()"
			:options="[
				{
					label: __('New Course'),
					icon: 'book-open',
					onClick() {
						showCourseModal = true
					},
				},
				{
					label: __('Import Course'),
					icon: 'upload',
					onClick() {
						router.push({
							name: 'NewDataImport',
							params: { doctype: 'LMS Course' },
						})
					},
				},
			]"
		>
			<template v-slot="{ open }">
				<Button variant="solid">
					<template #prefix>
						<Plus class="h-4 w-4 stroke-1.5" />
					</template>
					{{ __('Create') }}
					<template #suffix>
						<ChevronDown
							:class="[
								'w-4 h-4 stroke-1.5 ml-1 transform transition-transform',
								open ? 'rotate-180' : '',
							]"
						/>
					</template>
				</Button>
			</template>
		</Dropdown>
	</header>
	<MembershipUpsell class="mx-5 mt-4" />
	<LowCreditAlert class="mx-5 mt-4" />
	<div class="p-5 pb-10">
		<div
			class="flex flex-col lg:flex-row space-y-4 lg:space-y-0 lg:items-center justify-between mb-5"
		>
			<div class="text-lg text-ink-gray-9 font-semibold">
				{{ __('All Courses') }}
			</div>
			<div
				class="flex flex-col space-y-3 lg:space-y-0 lg:flex-row lg:items-center lg:space-x-4"
			>
				<TabButtons :buttons="courseTabs" v-model="currentTab" class="w-fit" />

				<div class="grid grid-cols-2 gap-2">
					<FormControl
						v-model="title"
						:placeholder="__('Search')"
						type="text"
						class="w-full lg:min-w-0 lg:w-32 xl:w-40"
						@input="updateCourses()"
					/>
					<div class="w-full lg:min-w-0 lg:w-32 xl:w-40">
						<Select
							v-if="categories.length"
							v-model="currentCategory"
							:options="categories"
							:placeholder="__('Category')"
							@update:modelValue="updateCourses()"
						/>
					</div>
				</div>

				<Tooltip v-if="!isCeuTab" :text="__('Only show courses that offer a certificate')">
					<FormControl
						type="checkbox"
						v-model="certification"
						:label="__('Certification')"
						@change="updateCourses()"
					/>
				</Tooltip>
			</div>
		</div>
		<div
			v-if="activeResource.data?.length"
			class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4"
			:class="isCeuTab ? 'gap-5' : 'gap-8'"
		>
			<template v-if="isCeuTab">
				<router-link
					v-for="event in ceuEvents.data"
					:to="{ name: 'EventDetail', params: { eventName: event.name } }"
				>
					<EventCard :batch="event" />
				</router-link>
			</template>
			<template v-else>
				<router-link
					v-for="course in courses.data"
					:to="{ name: 'CourseDetail', params: { courseName: course.name } }"
				>
					<CourseCard :course="course" />
				</router-link>
			</template>
		</div>
		<EmptyState v-else-if="!activeResource.list.loading" :type="isCeuTab ? 'Events' : 'Courses'" />
		<div
			v-if="!activeResource.list.loading && activeResource.hasNextPage"
			class="flex justify-center mt-5"
		>
			<Button @click="activeResource.next()">
				{{ __('Load More') }}
			</Button>
		</div>
	</div>
	<NewCourseModal
		v-if="showCourseModal"
		v-model="showCourseModal"
		:courses="courses"
	/>
</template>
<script setup>
import {
	Breadcrumbs,
	Button,
	call,
	createListResource,
	Dropdown,
	FormControl,
	Select,
	TabButtons,
	Tooltip,
	usePageMeta,
} from 'frappe-ui'
import { computed, inject, onMounted, ref, watch } from 'vue'
import { ChevronDown, Plus } from 'lucide-vue-next'
import { sessionStore } from '@/stores/session'
import { canCreateCourse } from '@/utils'
import CourseCard from '@/components/CourseCard.vue'
import EventCard from '@/pages/Events/components/EventCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import { useRouter } from 'vue-router'
import NewCourseModal from '@/pages/Courses/NewCourseModal.vue'
import MembershipUpsell from '@/components/MembershipUpsell.vue'
import LowCreditAlert from '@/components/LowCreditAlert.vue'

const user = inject('$user')
const start = ref(0)
const pageLength = ref(30)
const categories = ref([
	{
		label: '',
		value: null,
	},
])
const currentCategory = ref(null)
const title = ref('')
const certification = ref(false)
const filters = ref({})
const currentTab = ref('live')
const { brand } = sessionStore()
const courseCount = ref(0)
const router = useRouter()
const showCourseModal = ref(false)

onMounted(() => {
	setFiltersFromQuery()
	updateCourses()
	getCourseCount()
})

const setFiltersFromQuery = () => {
	let queries = new URLSearchParams(location.search)
	title.value = queries.get('title') || ''
	currentCategory.value = queries.get('category') || null
	certification.value = queries.get('certification') || false
	if (queries.get('newCourse') == '1') {
		showCourseModal.value = true
	}
}

const courses = createListResource({
	doctype: 'LMS Course',
	url: 'lms.lms.utils.get_courses',
	cache: ['courses', user.data?.name],
	pageLength: pageLength.value,
	start: start.value,
})

const ceuEvents = createListResource({
	doctype: 'LMS Event',
	url: 'lms.lms.utils.get_events',
	cache: ['ceu_events', user.data?.name],
	pageLength: 20,
	start: 0,
})

const isCeuTab = computed(() => currentTab.value === 'ceu_events')
const activeResource = computed(() => isCeuTab.value ? ceuEvents : courses)

const setCategories = (data) => {
	let allCategories = data.map((course) => course.category)
	allCategories = allCategories.filter(
		(category, index) => allCategories.indexOf(category) === index && category
	)
	if (categories.value.length <= allCategories.length) {
		updateCategories(data)
	}
}

const getCourseCount = () => {
	if (!user.data) return
	if (!user.data.is_moderator) return
	call('frappe.client.get_count', {
		doctype: 'LMS Course',
	}).then((data) => {
		courseCount.value = data
	})
}

const updateCourses = () => {
	updateFilters()

	if (isCeuTab.value) {
		let eventFilters = {
			credit_hours: ['>', 0],
			published: 1,
		}
		if (title.value) {
			eventFilters.title = ['like', `%${title.value}%`]
		}
		if (currentCategory.value) {
			eventFilters.category = currentCategory.value
		}
		ceuEvents.update({ filters: eventFilters })
		ceuEvents.reload()
	} else {
		courses.update({
			filters: filters.value,
		})
		courses.reload().then((data) => {
			setCategories(data)
		})
	}
}

const updateFilters = () => {
	updateCategoryFilter()
	updateTitleFilter()
	updateCertificationFilter()
	updateTabFilter()
	updateStudentFilter()
	setQueryParams()
}

const updateCategoryFilter = () => {
	if (currentCategory.value) {
		filters.value['category'] = currentCategory.value
	} else {
		delete filters.value['category']
	}
}

const updateTitleFilter = () => {
	if (title.value) {
		filters.value['title'] = ['like', `%${title.value}%`]
	} else {
		delete filters.value['title']
	}
}

const updateCertificationFilter = () => {
	if (certification.value) {
		filters.value['certification'] = 1
	} else {
		delete filters.value['certification']
	}
}

const updateTabFilter = () => {
	delete filters.value['live']
	delete filters.value['created']
	delete filters.value['upcoming']

	if (currentTab.value == 'enrolled' && user.data?.is_student) {
		filters.value['enrolled'] = 1
		delete filters.value['published']
	} else {
		delete filters.value['published']
		delete filters.value['enrolled']

		if (currentTab.value == 'live') {
			filters.value['published'] = 1
			filters.value['upcoming'] = 0
			filters.value['live'] = 1
		} else if (currentTab.value == 'created') {
			filters.value['created'] = 1
		} else if (currentTab.value == 'unpublished') {
			filters.value['published'] = 0
		}
	}
}

const updateStudentFilter = () => {
	if (!user.data || (user.data?.is_student && currentTab.value != 'enrolled')) {
		filters.value['published'] = 1
	}
}

const setQueryParams = () => {
	let queries = new URLSearchParams(location.search)
	let filterKeys = {
		title: title.value,
		category: currentCategory.value,
		certification: certification.value,
	}

	Object.keys(filterKeys).forEach((key) => {
		if (filterKeys[key]) {
			queries.set(key, filterKeys[key])
		} else {
			queries.delete(key)
		}
	})

	let queryString = ''
	if (queries.toString()) {
		queryString = `?${queries.toString()}`
	}

	history.replaceState({}, '', `${location.pathname}${queryString}`)
}

const updateCategories = (data) => {
	data.forEach((course) => {
		if (
			course.category &&
			!categories.value.find((category) => category.value === course.category)
		)
			categories.value.push({
				label: course.category,
				value: course.category,
			})
	})
}

watch(currentTab, () => {
	updateCourses()
})

const courseTabs = computed(() => {
	let tabs = [
		{
			label: __('Live'),
			value: 'ceu_events',
		},
		{
			label: __('On-demand'),
			value: 'live',
		},
	]
	if (
		user.data?.is_moderator
	) {
		tabs.push({ label: __('Created'), value: 'created' })
		tabs.push({ label: __('Unpublished'), value: 'unpublished' })
	} else if (user.data) {
		tabs.push({ label: __('Enrolled'), value: 'enrolled' })
	}
	return tabs
})

const breadcrumbs = computed(() => [
	{
		label: __('Courses'),
		route: { name: 'Courses' },
	},
])

usePageMeta(() => {
	return {
		title: __('Courses'),
		icon: brand.favicon,
	}
})
</script>

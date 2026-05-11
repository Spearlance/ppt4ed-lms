<template>
	<header
		class="sticky flex items-center justify-between top-0 z-10 border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />
		<Button v-if="canCreate" variant="solid" @click="showResourceModal = true">
			<template #prefix>
				<Plus class="h-4 w-4 stroke-1.5" />
			</template>
			{{ __('Create Resource') }}
		</Button>
	</header>
	<div class="p-5 pb-10">
		<div
			class="flex flex-col lg:flex-row space-y-4 lg:space-y-0 lg:items-center justify-between mb-5"
		>
			<div class="text-lg text-ink-gray-9 font-semibold">
				{{ __('Free Resources') }}
			</div>
			<div
				class="flex flex-col space-y-3 lg:space-y-0 lg:flex-row lg:items-center lg:space-x-4"
			>
				<TabButtons
					:buttons="audienceTabs"
					v-model="currentAudience"
					class="w-fit"
				/>

				<div class="grid grid-cols-2 gap-2">
					<FormControl
						v-model="title"
						:placeholder="__('Search')"
						type="text"
						class="w-full lg:min-w-0 lg:w-32 xl:w-40"
						@input="updateResources()"
					/>
					<div class="w-full lg:min-w-0 lg:w-32 xl:w-40">
						<Select
							v-model="currentType"
							:options="typeOptions"
							:placeholder="__('Type')"
							@update:modelValue="updateResources()"
						/>
					</div>
				</div>

				<Tooltip
					v-if="user.data"
					:text="__('Only show resources you have claimed')"
				>
					<FormControl
						type="checkbox"
						v-model="onlyClaimed"
						:label="__('My Resources')"
						@change="updateResources()"
					/>
				</Tooltip>
			</div>
		</div>
		<div
			v-if="resources.data?.length"
			class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-8"
		>
			<router-link
				v-for="resource in resources.data"
				:key="resource.name"
				:to="{
					name: 'ResourceDetail',
					params: { resourceName: resource.name },
				}"
			>
				<CourseCard :course="resource" />
			</router-link>
		</div>
		<EmptyState v-else-if="!resources.list.loading" type="Resources" />
		<div
			v-if="!resources.list.loading && resources.hasNextPage"
			class="flex justify-center mt-5"
		>
			<Button @click="resources.next()">
				{{ __('Load More') }}
			</Button>
		</div>
	</div>
	<NewResourceModal
		v-if="showResourceModal"
		v-model="showResourceModal"
		:resources="resources"
	/>
</template>
<script setup>
import {
	Breadcrumbs,
	Button,
	createListResource,
	FormControl,
	Select,
	TabButtons,
	Tooltip,
	usePageMeta,
} from 'frappe-ui'
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Plus } from 'lucide-vue-next'
import { sessionStore } from '@/stores/session'
import { canCreateCourse } from '@/utils'
import CourseCard from '@/components/CourseCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import NewResourceModal from '@/pages/Resources/NewResourceModal.vue'

const user = inject('$user')
const { brand } = sessionStore()
const route = useRoute()
const router = useRouter()
const showResourceModal = ref(false)
const canCreate = computed(() => canCreateCourse())
const title = ref('')
const currentType = ref(null)
const currentAudience = ref(route.query.audience || null)
const onlyClaimed = ref(route.query.claimed === '1')

const typeOptions = [
	{ label: __('All Types'), value: null },
	{ label: __('Video'), value: 'Video' },
	{ label: __('Download'), value: 'Download' },
	{ label: __('Article'), value: 'Article' },
	{ label: __('Mini-Course'), value: 'Mini-Course' },
	{ label: __('Template'), value: 'Template' },
]

const audienceTabs = [
	{ label: __('All'), value: null },
	{ label: __('Healthcare'), value: 'Healthcare Professionals' },
	{ label: __('Educators'), value: 'Educators' },
	{ label: __('Caregivers'), value: 'Parents / Caregivers' },
]

onMounted(() => {
	updateResources()
})

const resources = createListResource({
	doctype: 'LMS Course',
	url: 'lms.lms.utils.get_resources',
	cache: ['resources'],
	pageLength: 30,
})

const updateResources = () => {
	let filters = {}

	if (currentType.value) {
		filters.resource_type = currentType.value
	}
	if (currentAudience.value) {
		filters.audience = currentAudience.value
	}
	if (onlyClaimed.value) {
		filters.only_enrolled = 1
	}
	if (title.value) {
		filters.title = ['like', `%${title.value}%`]
	}

	resources.update({ filters })
	resources.reload()
	setQueryParams()
}

const setQueryParams = () => {
	const queries = new URLSearchParams(location.search)
	if (currentAudience.value) {
		queries.set('audience', currentAudience.value)
	} else {
		queries.delete('audience')
	}
	if (onlyClaimed.value) {
		queries.set('claimed', '1')
	} else {
		queries.delete('claimed')
	}
	const queryString = queries.toString() ? `?${queries.toString()}` : ''
	history.replaceState({}, '', `${location.pathname}${queryString}`)
}

watch(currentAudience, () => {
	updateResources()
})

const breadcrumbs = computed(() => [
	{
		label: __('Resources'),
		route: { name: 'Resources' },
	},
])

usePageMeta(() => {
	return {
		title: __('Free Resources'),
		icon: brand.favicon,
	}
})
</script>

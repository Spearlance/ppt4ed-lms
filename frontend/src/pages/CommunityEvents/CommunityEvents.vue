<template>
	<header
		class="sticky flex items-center justify-between top-0 z-10 border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />
		<Button v-if="canCreate" variant="solid" @click="showNewModal = true">
			<template #prefix>
				<Plus class="h-4 w-4 stroke-1.5" />
			</template>
			{{ __('New Community Event') }}
		</Button>
	</header>
	<div class="p-5 pb-10">
		<div
			class="flex flex-col lg:flex-row space-y-4 lg:space-y-0 lg:items-center justify-between mb-5"
		>
			<div class="text-lg text-ink-gray-9 font-semibold">
				{{ __('Community Events') }}
			</div>
			<div
				class="flex flex-col space-y-3 lg:space-y-0 lg:flex-row lg:items-center lg:space-x-4"
			>
				<TabButtons
					:buttons="tabs"
					v-model="currentTab"
					class="w-fit"
				/>
				<FormControl
					v-model="searchTitle"
					:placeholder="__('Search by Title')"
					type="text"
					class="min-w-40 lg:w-44"
					@input="reload"
				/>
			</div>
		</div>

		<div
			v-if="events.data?.length"
			class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5"
		>
			<router-link
				v-for="ev in events.data"
				:key="ev.name"
				:to="{ name: 'CommunityEventForm', params: { slug: ev.name } }"
				class="block border rounded-lg overflow-hidden bg-surface-white hover:shadow-md transition"
			>
				<div
					v-if="ev.image"
					class="h-40 bg-cover bg-center"
					:style="{ backgroundImage: `url(${ev.image})` }"
				/>
				<div v-else class="h-40 bg-surface-gray-2 flex items-center justify-center text-ink-gray-5">
					<Users class="w-8 h-8 stroke-1.5" />
				</div>
				<div class="p-4">
					<div class="flex items-center gap-2 mb-1.5">
						<Badge
							:theme="ev.published ? 'green' : 'gray'"
							:label="ev.published ? __('Published') : __('Draft')"
							size="sm"
						/>
					</div>
					<h3 class="font-semibold text-ink-gray-9 mb-1 line-clamp-2">{{ ev.title }}</h3>
					<div class="text-sm text-ink-gray-6">
						{{ formatDate(ev.start_date) }}
						<span v-if="ev.end_date && ev.end_date !== ev.start_date">
							&mdash; {{ formatDate(ev.end_date) }}
						</span>
					</div>
					<div class="text-sm text-ink-gray-6 mt-1">
						{{ ev.confirmed_attendees }}
						{{ __(' attendees') }}
						<span v-if="ev.max_attendees > 0">/ {{ ev.max_attendees }}</span>
					</div>
				</div>
			</router-link>
		</div>
		<div
			v-else-if="!events.loading"
			class="text-center py-16 text-ink-gray-6"
		>
			{{ __('No community events yet. Create your first one to share it with families.') }}
		</div>
	</div>

	<NewCommunityEventModal
		v-if="showNewModal"
		v-model="showNewModal"
		@created="onCreated"
	/>
</template>

<script setup>
import { computed, inject, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
	Badge,
	Breadcrumbs,
	Button,
	createResource,
	FormControl,
	TabButtons,
	usePageMeta,
} from 'frappe-ui'
import { Plus, Users } from 'lucide-vue-next'
import { sessionStore } from '@/stores/session'
import NewCommunityEventModal from '@/pages/CommunityEvents/components/NewCommunityEventModal.vue'

const user = inject('$user')
const dayjs = inject('$dayjs')
const { brand } = sessionStore()
const router = useRouter()

const showNewModal = ref(false)
const searchTitle = ref('')
const currentTab = ref('all')

const tabs = [
	{ label: __('All'), value: 'all' },
	{ label: __('Published'), value: 'published' },
	{ label: __('Drafts'), value: 'draft' },
]

const filters = computed(() => {
	const f = {}
	if (searchTitle.value) f.title = ['like', `%${searchTitle.value}%`]
	if (currentTab.value === 'published') f.published = 1
	if (currentTab.value === 'draft') f.published = 0
	return f
})

const events = createResource({
	url: 'lms.lms.community_event.get_community_events',
	auto: true,
	makeParams() {
		return {
			filters: JSON.stringify(filters.value),
			page_length: 100,
		}
	},
})

const reload = () => events.reload()

const onCreated = (slug) => {
	router.push({ name: 'CommunityEventForm', params: { slug } })
}

const canCreate = computed(() => !!user.data?.is_moderator)

const formatDate = (d) => (d ? dayjs(d).format('MMM D, YYYY') : '')

const breadcrumbs = computed(() => [
	{ label: __('Community Events'), route: { name: 'CommunityEvents' } },
])

usePageMeta(() => ({
	title: __('Community Events'),
	icon: brand.favicon,
}))

onMounted(reload)
</script>

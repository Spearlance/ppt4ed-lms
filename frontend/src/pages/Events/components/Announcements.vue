<template>
	<div class="w-[90%] lg:w-[75%] mx-auto mt-5">
		<div class="flex items-center justify-between mb-5">
			<div class="text-ink-gray-9 font-semibold text-lg">
				{{ __('Announcements') }}
			</div>
			<Button
				v-if="canPost"
				variant="solid"
				@click="$emit('open-modal')"
			>
				<template #prefix>
					<Megaphone class="w-4 h-4 stroke-1.5" />
				</template>
				{{ __('Make Announcement') }}
			</Button>
		</div>
		<div v-if="communications.data?.length">
			<div v-for="comm in communications.data" :key="comm.communication_date">
				<div class="mb-8">
					<div class="flex items-center justify-between mb-2">
						<div class="flex items-center">
							<Avatar :label="comm.sender_full_name" size="lg" />
							<div class="ml-2">
								<div class="text-ink-gray-8 text-sm font-medium">
									{{ comm.sender_full_name }}
								</div>
								<div class="text-ink-gray-6 text-sm">
									{{ comm.subject }}
								</div>
							</div>
						</div>
						<div class="text-sm text-ink-gray-6">
							{{ timeAgo(comm.communication_date) }}
						</div>
					</div>
					<div
						class="prose prose-sm bg-surface-menu-bar !min-w-full px-4 py-2 rounded-md"
						v-html="comm.content"
					></div>
				</div>
			</div>
		</div>
		<div
			v-else
			class="border border-dashed border-outline-gray-2 rounded-md py-12 px-6 text-center"
		>
			<Megaphone class="w-8 h-8 stroke-1.5 mx-auto text-ink-gray-5 mb-2" />
			<div class="text-ink-gray-7 leading-5 mb-3">
				{{
					canPost
						? __('No announcements yet. Post one to reach your enrolled attendees.')
						: __('No announcements have been made yet for this event')
				}}
			</div>
			<Button v-if="canPost" variant="solid" @click="$emit('open-modal')">
				{{ __('Post the first announcement') }}
			</Button>
		</div>
	</div>
</template>
<script setup>
import { createResource, Avatar, Button } from 'frappe-ui'
import { Megaphone } from 'lucide-vue-next'
import { timeAgo } from '@/utils'

const props = defineProps({
	batch: {
		type: Object,
		required: true,
	},
	canPost: {
		type: Boolean,
		default: false,
	},
})

defineEmits(['open-modal'])

const communications = createResource({
	url: 'lms.lms.api.get_announcements',
	makeParams() {
		return {
			batch: props.batch.data?.name,
		}
	},
	auto: true,
	cache: ['announcement', props.batch],
})

defineExpose({
	reload: () => communications.reload(),
})
</script>
<style>
.prose-sm p {
	margin: 0 0 0.5rem;
}
</style>

<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Private registration link'),
			size: 'lg',
		}"
	>
		<template #body-content>
			<div class="space-y-4 text-sm text-ink-gray-7">
				<p>
					{{ __('Share this link with a group whose seats are already paid for. Anyone who opens it can create an account (or log in) and register for free. The event does not need to be published, so it stays out of the catalog.') }}
				</p>

				<ErrorMessage v-if="errorMessage" :message="errorMessage" />

				<div v-if="link.loading && !link.data" class="text-ink-gray-5">
					{{ __('Loading...') }}
				</div>

				<div
					v-else-if="link.data?.paid_event"
					class="rounded-md bg-surface-amber-2 px-3 py-2 text-ink-amber-3"
				>
					{{ __('This is a paid event. Private links are for free or prepaid events. Turn off Paid Event in the event settings to use one.') }}
				</div>

				<template v-else-if="link.data?.enabled">
					<div class="flex items-end gap-2">
						<FormControl
							class="flex-1"
							:label="__('Link')"
							type="text"
							:model-value="link.data.url"
							readonly
							data-testid="private-link-url"
						/>
						<Button :label="__('Copy')" variant="solid" @click="copyLink">
							{{ __('Copy') }}
						</Button>
					</div>
					<p
						v-if="link.data.published"
						class="rounded-md bg-surface-amber-2 px-3 py-2 text-ink-amber-3"
					>
						{{ __('This event is published, so it is also visible in the catalog. Unpublish it to keep it private.') }}
					</p>
					<div class="flex items-center justify-between border-t border-outline-gray-2 pt-3">
						<span class="text-xs text-ink-gray-5">
							{{ __('Resetting makes a new link; the old one stops working. People already registered stay registered.') }}
						</span>
						<div class="flex gap-2 shrink-0 ml-3">
							<Button :label="__('Reset link')" :loading="saving" @click="update(1, 1)">
								{{ __('Reset link') }}
							</Button>
							<Button
								:label="__('Turn off')"
								theme="red"
								:loading="saving"
								@click="update(0, 0)"
							>
								{{ __('Turn off') }}
							</Button>
						</div>
					</div>
				</template>

				<div v-else-if="link.data">
					<Button
						:label="__('Create private link')"
						variant="solid"
						:loading="saving"
						@click="update(1, 0)"
					>
						{{ __('Create private link') }}
					</Button>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
// Admin dialog for an event's private registration link. The link itself is
// derived server-side (lms/lms/event_private_link.py); this only turns it on
// or off, resets it and copies it.
import { Button, call, createResource, Dialog, ErrorMessage, FormControl, toast } from 'frappe-ui'
import { ref } from 'vue'

const show = defineModel()

const props = defineProps({
	event: { type: String, required: true },
})

const saving = ref(false)
const errorMessage = ref('')

const link = createResource({
	url: 'lms.lms.event_private_link.get_private_link',
	makeParams: () => ({ event: props.event }),
	auto: true,
})

async function update(enabled, reset) {
	errorMessage.value = ''
	saving.value = true
	try {
		const state = await call('lms.lms.event_private_link.set_private_link', {
			event: props.event,
			enabled,
			reset,
		})
		link.setData(state)
	} catch (err) {
		errorMessage.value =
			String(err?.messages?.[0] || err?.message || '').replace(/<[^>]+>/g, '') ||
			__('Could not update the link. Please try again.')
	} finally {
		saving.value = false
	}
}

async function copyLink() {
	try {
		await navigator.clipboard.writeText(link.data.url)
		toast.success(__('Link copied'))
	} catch (e) {
		toast.error(__('Could not copy. Select the link and copy it manually.'))
	}
}
</script>

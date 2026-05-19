<template>
	<div>
		<div
			class="group flex items-center gap-2 border-b py-1.5 pr-2 last:border-b-0 hover:bg-surface-gray-1"
			:style="{ paddingLeft: depth * 20 + 8 + 'px' }"
		>
			<button
				class="flex h-5 w-5 items-center justify-center text-ink-gray-5"
				:class="{ invisible: !hasChildren }"
				@click="$emit('toggle', node.name)"
			>
				<ChevronDown v-if="isOpen" class="h-4 w-4" />
				<ChevronRight v-else class="h-4 w-4" />
			</button>
			<Folder
				v-if="hasChildren"
				class="h-4 w-4 shrink-0 text-ink-amber-3"
			/>
			<FolderClosed
				v-else
				class="h-4 w-4 shrink-0 text-ink-gray-5"
			/>
			<div class="min-w-0 flex-1 truncate text-sm">
				<span class="font-medium text-ink-gray-9">{{ node.label }}</span>
				<span
					v-if="node.subtree_resource_count"
					class="ml-2 text-xs text-ink-gray-5"
				>
					{{ node.subtree_resource_count }}
					{{ node.subtree_resource_count === 1 ? __('resource') : __('resources') }}
				</span>
			</div>
			<div class="flex items-center gap-1 opacity-0 group-hover:opacity-100">
				<Button
					size="sm"
					variant="ghost"
					@click="$emit('add-child', node)"
					:tooltip="__('Add sub-category')"
				>
					<template #icon><Plus class="h-3.5 w-3.5" /></template>
				</Button>
				<Button
					size="sm"
					variant="ghost"
					@click="$emit('rename', node)"
					:tooltip="__('Rename')"
				>
					<template #icon><Pencil class="h-3.5 w-3.5" /></template>
				</Button>
				<Button
					size="sm"
					variant="ghost"
					@click="$emit('move', node)"
					:tooltip="__('Move')"
				>
					<template #icon><Move class="h-3.5 w-3.5" /></template>
				</Button>
				<Button
					size="sm"
					variant="ghost"
					theme="red"
					@click="$emit('delete', node)"
					:tooltip="__('Delete')"
				>
					<template #icon><Trash2 class="h-3.5 w-3.5" /></template>
				</Button>
			</div>
		</div>
		<template v-if="isOpen && hasChildren">
			<CategoryNode
				v-for="child in node.children"
				:key="child.name"
				:node="child"
				:depth="depth + 1"
				:expanded="expanded"
				@toggle="(n) => $emit('toggle', n)"
				@add-child="(n) => $emit('add-child', n)"
				@rename="(n) => $emit('rename', n)"
				@move="(n) => $emit('move', n)"
				@delete="(n) => $emit('delete', n)"
			/>
		</template>
	</div>
</template>

<script setup>
import { computed } from 'vue'
import { Button } from 'frappe-ui'
import {
	ChevronDown,
	ChevronRight,
	Folder,
	FolderClosed,
	Move,
	Pencil,
	Plus,
	Trash2,
} from 'lucide-vue-next'

const props = defineProps({
	node: { type: Object, required: true },
	depth: { type: Number, default: 0 },
	expanded: { type: Set, required: true },
})

defineEmits(['toggle', 'add-child', 'rename', 'move', 'delete'])

const hasChildren = computed(() => (props.node.children?.length || 0) > 0)
const isOpen = computed(() => props.expanded.has(props.node.name))
</script>

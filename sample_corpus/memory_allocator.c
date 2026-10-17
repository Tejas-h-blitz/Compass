#include <stdio.h>
#include <stddef.h>
#include <stdbool.h>

typedef struct BlockHeader {
    size_t size;
    bool is_free;
    struct BlockHeader* next;
} BlockHeader;

#define POOL_SIZE 65536
static char memory_pool[POOL_SIZE];
static BlockHeader* free_list = (BlockHeader*)memory_pool;

void init_allocator() {
    free_list->size = POOL_SIZE - sizeof(BlockHeader);
    free_list->is_free = true;
    free_list->next = NULL;
}

void* my_malloc(size_t size) {
    BlockHeader* curr = free_list;
    while (curr) {
        if (curr->is_free && curr->size >= size) {
            curr->is_free = false;
            return (void*)((char*)curr + sizeof(BlockHeader));
        }
        curr = curr->next;
    }
    return NULL; // Out of memory
}

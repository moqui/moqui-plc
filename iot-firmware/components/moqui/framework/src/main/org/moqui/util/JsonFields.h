#ifndef JSON_FIELDS_H
#define JSON_FIELDS_H
#include <stdbool.h>
#include <stddef.h>
/* Bounded, allocation-free JSON object reader. Returned spans borrow input. */
bool JsonFields_Valid(const char *json, size_t len);
bool JsonFields_Find(const char *json, size_t len, const char *key,
                     const char **value, size_t *value_len);
#endif

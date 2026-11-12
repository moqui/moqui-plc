#include "JsonFields.h"
#include <string.h>

typedef struct { const char *p; const char *end; } Reader;
static void space(Reader *r) {
    while (r->p < r->end && (*r->p == ' ' || *r->p == '\t' || *r->p == '\r' || *r->p == '\n')) { ++r->p; }
}
static bool digit(char c) { return c >= '0' && c <= '9'; }
static bool string(Reader *r) {
    if (r->p == r->end || *r->p++ != '"') { return false; }
    while (r->p < r->end) {
        unsigned char c = (unsigned char)*r->p++;
        if (c == '"') { return true; }
        if (c < 32U) { return false; }
        if (c == '\\') {
            if (r->p == r->end) { return false; }
            c = (unsigned char)*r->p++;
            if (c == 'u') {
                for (unsigned i = 0; i < 4; ++i) {
                    if (r->p == r->end) { return false; }
                    char h = *r->p++;
                    if (!digit(h) && !(h >= 'a' && h <= 'f') && !(h >= 'A' && h <= 'F')) { return false; }
                }
            } else if (strchr("\"\\/bfnrt", c) == NULL) { return false; }
        }
    }
    return false;
}
static bool value(Reader *r, unsigned depth) {
    space(r);
    if (r->p == r->end || depth > 8U) { return false; }
    char c = *r->p;
    if (c == '"') { return string(r); }
    if (c == '{' || c == '[') {
        char close = c == '{' ? '}' : ']';
        ++r->p;
        space(r);
        if (r->p < r->end && *r->p == close) { ++r->p; return true; }
        for (;;) {
            if (c == '{') {
                if (!string(r)) { return false; }
                space(r);
                if (r->p == r->end || *r->p++ != ':') { return false; }
            }
            if (!value(r, depth + 1U)) { return false; }
            space(r);
            if (r->p == r->end) { return false; }
            if (*r->p == close) { ++r->p; return true; }
            if (*r->p++ != ',') { return false; }
            space(r);
        }
    }
    const char *literal = c == 't' ? "true" : c == 'f' ? "false" : c == 'n' ? "null" : NULL;
    if (literal) {
        size_t n = strlen(literal);
        if ((size_t)(r->end - r->p) < n || memcmp(r->p, literal, n) != 0) { return false; }
        r->p += n;
        return true;
    }
    if (c == '-') { ++r->p; }
    if (r->p == r->end || !digit(*r->p)) { return false; }
    if (*r->p == '0') { ++r->p; }
    else { while (r->p < r->end && digit(*r->p)) { ++r->p; } }
    if (r->p < r->end && *r->p == '.') {
        ++r->p;
        if (r->p == r->end || !digit(*r->p)) { return false; }
        while (r->p < r->end && digit(*r->p)) { ++r->p; }
    }
    if (r->p < r->end && (*r->p == 'e' || *r->p == 'E')) {
        ++r->p;
        if (r->p < r->end && (*r->p == '+' || *r->p == '-')) { ++r->p; }
        if (r->p == r->end || !digit(*r->p)) { return false; }
        while (r->p < r->end && digit(*r->p)) { ++r->p; }
    }
    return true;
}
bool JsonFields_Valid(const char *json, size_t len) {
    if (!json || len == 0U) { return false; }
    Reader r = {json, json + len};
    space(&r);
    if (r.p == r.end || *r.p != '{' || !value(&r, 0U)) { return false; }
    space(&r);
    return r.p == r.end;
}
bool JsonFields_Find(const char *json, size_t len, const char *key,
                     const char **out, size_t *out_len) {
    if (!key || !out || !out_len || !JsonFields_Valid(json, len)) { return false; }
    Reader r = {json, json + len};
    space(&r);
    ++r.p;
    space(&r);
    while (r.p < r.end && *r.p != '}') {
        const char *k = r.p + 1;
        if (!string(&r)) { return false; }
        size_t key_len = (size_t)(r.p - k - 1);
        space(&r); ++r.p; space(&r);
        const char *v = r.p;
        if (!value(&r, 0U)) { return false; }
        if (strlen(key) == key_len && memcmp(k, key, key_len) == 0) {
            *out = v;
            *out_len = (size_t)(r.p - v);
            return true;
        }
        space(&r);
        if (*r.p == '}') { break; }
        ++r.p;
        space(&r);
    }
    return false;
}

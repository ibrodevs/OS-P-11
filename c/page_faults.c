#define _POSIX_C_SOURCE 200809L
#define _DEFAULT_SOURCE
/* Page fault experiment: getrusage + /proc/self/stat on Linux.
 * Modes: anonymous writable mapping; file-backed clean readable mapping.
 * File mode can show major faults when real storage I/O is needed.
 * No global cache dropping and no root privileges required.
 */
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

typedef struct { unsigned long long minor, major; } ProcFaults;
typedef struct { struct rusage usage; ProcFaults proc; struct timespec clock; } Snapshot;

static void usage(const char *name) {
    fprintf(stderr, "Usage: %s [--mode anon|file] [--pattern sequential|random|local] "
            "[--mb 32] [--passes 3] [--seed 42] [--dir PATH] [--evict-between-passes]\n", name);
}
static long number(const char *s, long lo, long hi) {
    char *end = NULL;
    errno = 0;
    long n = strtol(s, &end, 10);
    if (errno || !s[0] || !end || *end || n < lo || n > hi) {
        fprintf(stderr, "Invalid number: %s (range %ld..%ld)\n", s, lo, hi);
        exit(2);
    }
    return n;
}
static void check(int ok, const char *context) {
    if (!ok) { perror(context); exit(1); }
}
static ProcFaults proc_faults(void) {
    ProcFaults result = {0, 0};
    FILE *file = fopen("/proc/self/stat", "r");
    check(file != NULL, "open /proc/self/stat");
    char line[8192];
    check(fgets(line, sizeof line, file) != NULL, "read /proc/self/stat");
    fclose(file);
    /* A process name in (comm) can contain spaces and closing parentheses.
       Skip through the *last* ')' before tokenizing fields 3 onward. */
    char *start = strrchr(line, ')');
    if (!start) { fprintf(stderr, "Invalid /proc/self/stat\n"); exit(1); }
    char *save = NULL;
    int field = 3;
    for (char *token = strtok_r(start + 1, " \t\n", &save); token;
         token = strtok_r(NULL, " \t\n", &save), ++field) {
        if (field == 10) result.minor = strtoull(token, NULL, 10);
        if (field == 12) { result.major = strtoull(token, NULL, 10); return result; }
    }
    fprintf(stderr, "Missing /proc/self/stat fields\n");
    exit(1);
}
static Snapshot snapshot(void) {
    Snapshot s;
    check(getrusage(RUSAGE_SELF, &s.usage) == 0, "getrusage");
    s.proc = proc_faults();
    check(clock_gettime(CLOCK_MONOTONIC, &s.clock) == 0, "clock_gettime");
    return s;
}
static double elapsed(const struct timespec *start, const struct timespec *finish) {
    return (double)(finish->tv_sec - start->tv_sec) +
           (double)(finish->tv_nsec - start->tv_nsec) / 1e9;
}
static uint64_t rand64(uint64_t *seed) {
    uint64_t x = *seed;
    x ^= x << 13;
    x ^= x >> 7;
    x ^= x << 17;
    return *seed = x;
}
int main(int argc, char **argv) {
    const char *mode = "anon", *pattern = "sequential", *directory = "/tmp";
    long mb = 32, passes = 3, seed_value = 42;
    int evict = 0;
    for (int a = 1; a < argc; ++a) {
        if (!strcmp(argv[a], "--evict-between-passes")) { evict = 1; continue; }
        if (a + 1 >= argc) { usage(argv[0]); return 2; }
        const char *value = argv[++a];
        if (!strcmp(argv[a-1], "--mode")) mode = value;
        else if (!strcmp(argv[a-1], "--pattern")) pattern = value;
        else if (!strcmp(argv[a-1], "--dir")) directory = value;
        else if (!strcmp(argv[a-1], "--mb")) mb = number(value, 1, 1024);
        else if (!strcmp(argv[a-1], "--passes")) passes = number(value, 1, 100);
        else if (!strcmp(argv[a-1], "--seed")) seed_value = number(value, 1, LONG_MAX);
        else { usage(argv[0]); return 2; }
    }
    if (strcmp(mode, "anon") && strcmp(mode, "file")) { usage(argv[0]); return 2; }
    if (strcmp(pattern, "sequential") && strcmp(pattern, "random") && strcmp(pattern, "local")) { usage(argv[0]); return 2; }
    if (evict && strcmp(mode, "file")) { fprintf(stderr, "--evict-between-passes only for file mode\n"); return 2; }
    const long system_page = sysconf(_SC_PAGESIZE);
    check(system_page > 0, "sysconf PAGESIZE");
    const size_t length = (size_t)mb * 1024u * 1024u;
    const size_t npages = length / (size_t)system_page;
    check(npages > 0, "pages");
    char *mapping = NULL;
    int fd = -1;
    char *path = NULL;
    if (!strcmp(mode, "file")) {
        size_t size = strlen(directory) + 40;
        path = malloc(size);
        check(path != NULL, "malloc path");
        snprintf(path, size, "%s/os-p11-faults-XXXXXX", directory);
        fd = mkstemp(path);
        check(fd != -1, "mkstemp (choose a disk-backed --dir)");
        /* Unlink immediately: file remains mapped and no cleanup is needed. */
        check(unlink(path) == 0, "unlink temp file");
        free(path);
        const size_t chunk = 64u * 1024u;
        char *zeros = calloc(1, chunk);
        check(zeros != NULL, "calloc write buffer");
        for (size_t at = 0; at < length; at += chunk) {
            size_t to_write = length - at < chunk ? length - at : chunk;
            ssize_t wrote = pwrite(fd, zeros, to_write, (off_t)at);
            check(wrote == (ssize_t)to_write, "pwrite test data");
        }
        free(zeros);
        check(fsync(fd) == 0, "fsync test data");
        mapping = mmap(NULL, length, PROT_READ, MAP_PRIVATE, fd, 0);
        check(mapping != MAP_FAILED, "mmap file");
        /* Hint to reclaim clean file cache; kernel may ignore the hint. */
        int rc = posix_fadvise(fd, 0, (off_t)length, POSIX_FADV_DONTNEED);
        if (rc) fprintf(stderr, "warning: posix_fadvise: %s\n", strerror(rc));
    } else {
        mapping = mmap(NULL, length, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        check(mapping != MAP_FAILED, "mmap anonymous");
    }
    size_t *permutation = NULL;
    if (!strcmp(pattern, "random")) {
        permutation = malloc(npages * sizeof *permutation);
        check(permutation != NULL, "malloc permutation");
        for (size_t i = 0; i < npages; i++) permutation[i] = i;
        uint64_t rng = (uint64_t)seed_value;
        for (size_t i = npages; i > 1; --i) {
            size_t j = (size_t)(rand64(&rng) % i);
            size_t t = permutation[i - 1]; permutation[i - 1] = permutation[j]; permutation[j] = t;
        }
    }
    volatile unsigned char *bytes = (volatile unsigned char *)mapping;
    volatile uint64_t checksum = 0;
    printf("pass,mode,pattern,mb,seconds,minor_getrusage,major_getrusage,minor_proc,major_proc,checksum\n");
    for (long p = 1; p <= passes; ++p) {
        Snapshot before = snapshot();
        const size_t hot = npages / 8 ? npages / 8 : 1;
        for (size_t i = 0; i < npages; ++i) {
            size_t page = i;
            if (!strcmp(pattern, "random")) page = permutation[i];
            else if (!strcmp(pattern, "local"))
                page = (i % 10 < 9) ? ((i / 10) % hot) : ((i / 10) % npages);
            size_t offset = page * (size_t)system_page;
            if (!strcmp(mode, "anon")) bytes[offset] = (unsigned char)(p + page);
            checksum += bytes[offset];
        }
        Snapshot after = snapshot();
        printf("%ld,%s,%s,%ld,%.6f,%ld,%ld,%llu,%llu,%" PRIu64 "\n",
               p, mode, pattern, mb, elapsed(&before.clock, &after.clock),
               after.usage.ru_minflt - before.usage.ru_minflt,
               after.usage.ru_majflt - before.usage.ru_majflt,
               after.proc.minor - before.proc.minor,
               after.proc.major - before.proc.major, (uint64_t)checksum);
        fflush(stdout);
        if (evict && p != passes) {
            check(madvise(mapping, length, MADV_DONTNEED) == 0, "madvise");
            int rc = posix_fadvise(fd, 0, (off_t)length, POSIX_FADV_DONTNEED);
            if (rc) fprintf(stderr, "warning: posix_fadvise: %s\n", strerror(rc));
        }
    }
    free(permutation);
    check(munmap(mapping, length) == 0, "munmap");
    if (fd >= 0) close(fd);
    return 0;
}

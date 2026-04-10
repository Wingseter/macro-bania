#include <iostream>
#include <vector>
#include <algorithm>

int main() {
    std::vector<int> numbers = {5, 3, 8, 1, 9, 2, 7, 4, 6};

    std::cout << "Before sorting: ";
    for (int n : numbers) {
        std::cout << n << " ";
    }
    std::cout << std::endl;

    std::sort(numbers.begin(), numbers.end());

    std::cout << "After sorting:  ";
    for (int n : numbers) {
        std::cout << n << " ";
    }
    std::cout << std::endl;

    return 0;
}
